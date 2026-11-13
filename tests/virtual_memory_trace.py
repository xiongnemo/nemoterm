"""Virtual commit/release diagnostic for pre-selected owned-process ranges."""
import hashlib
import time
from pathlib import Path
import frida
from allocation_census import AllocationCensus
from native_test_utils import mmap,memory_sample
from fixture_io import write_snapshot
from frida_test_utils import call_frida
from working_set_regions import private_regions,private_page_addresses,reservation_range,reservation_layout


class VirtualMemoryTrace(AllocationCensus):
    def checkpoint(self,phase):
        self.result['phase']=phase
        write_snapshot(self.path,self.result)
        print('Virtual memory trace:',phase,flush=True)

    def start(self):
        self.checkpoint('select-pre-attach-reservations')
        before=private_regions(self.handle)
        candidates=[r for r in before['allocations'] if r['kind']=='private' and r['private_ws']>=65536]
        selected=candidates[:64]
        if not selected:raise RuntimeError('No sizeable pre-attach private reservations')
        ranges=[reservation_range(self.handle,int(r['allocation'],16)) for r in selected]
        self.result.update(observation='virtual-memory-events',before=before,
            scope=dict(pid=self.pid,ranges=ranges,event_capacity=4096),
            before_layouts=[reservation_layout(self.handle,r) for r in ranges],
            selection=dict(minimum_private_ws=65536,maximum_reservations=64,
                selected_reservations=len(selected),eligible_reservations=len(candidates)))
        folder=Path(__file__).resolve().parent
        files=('virtual_memory_probe.js','virtual_memory_trace.py','working_set_regions.py',
               'allocation_census.py','tabs_window_smoke.py','tab_workload_memory.py')
        self.result['source_sha256']={name:hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in files}
        self.checkpoint('attach-owned-frontend')
        self.session=call_frida('virtual-attach',frida.attach,self.pid)
        self.script=call_frida('virtual-create',self.session.create_script,
                               (folder/files[0]).read_text(encoding='utf-8'))
        self.script.on('message',lambda message,data:self.errors.append(message)
                       if message['type']=='error' else None)
        call_frida('virtual-load',self.script.load)
        self.checkpoint('initialize-native-hooks')
        self.result['initialized']=self.script.exports_sync.initialize(self.result['scope'])
        # Attaching and creating the script can grow existing target heaps.
        # Keep that interval separate from the subsequent terminal workload.
        self.result['observation_start_layouts']=[reservation_layout(self.handle,r) for r in ranges]
        self.result['observation_start_private_pages']=[hex(p) for p in private_page_addresses(self.handle)]
        self.result['observation_start_memory']=memory_sample(self.handle)
        self.checkpoint('observe-workload')

    def freeze(self):
        self.checkpoint('freeze-virtual-events')
        started=time.monotonic()
        snapshot=self.script.exports_sync.freeze();self.result['snapshot']=snapshot
        frozen=time.monotonic()
        self.checkpoint('query-selected-commitment-and-private-pages')
        after_layouts=[reservation_layout(self.handle,r) for r in self.result['scope']['ranges']]
        pages=private_page_addresses(self.handle)
        after=private_regions(self.handle)
        self.result.update(after_layouts=after_layouts,page_size=mmap.PAGESIZE,private_page_addresses=[hex(p) for p in pages],
            after=after,memory_after_freeze=memory_sample(self.handle),observer_errors=self.errors,
            timing=dict(freeze_rpc_seconds=frozen-started,metadata_after_freeze_seconds=time.monotonic()-frozen))
        if self.errors or not snapshot['valid'] or snapshot['active']:
            self.checkpoint('invalid-capture')
            raise RuntimeError('Virtual memory capture is invalid')
        before_private={e['allocation']:e['private_ws'] for e in self.result['before']['allocations']}
        changes=[]
        observation_pages=[int(p,16) for p in self.result['observation_start_private_pages']]
        for before_layout,observation_layout,after_layout in zip(
                self.result['before_layouts'],self.result['observation_start_layouts'],after_layouts):
            start,end=int(before_layout['start'],16),int(before_layout['end'],16)
            matching=[]
            for event in snapshot['events']:
                address=int(event['address'],16);size=int(event['bytes'])
                if (start<=address<end if size==0 else address<end and address+size>start):
                    matching.append(event['sequence'])
            changes.append(dict(start=before_layout['start'],end=before_layout['end'],reserved_bytes=end-start,
                before_committed_bytes=before_layout['committed_bytes'],after_committed_bytes=after_layout['committed_bytes'],
                observation_start_committed_bytes=observation_layout['committed_bytes'],
                before_private_ws=before_private.get(before_layout['start'],0),
                observation_start_private_ws=sum(start<=p<end for p in observation_pages)*mmap.PAGESIZE,
                after_private_ws=sum(start<=p<end for p in pages)*mmap.PAGESIZE,
                event_sequences=matching))
        self.result['reservation_changes']=changes
        self.result['newly_observed_private_allocations']=[e for e in after['allocations']
            if e['kind']=='private' and e['allocation'] not in before_private]
        self.result['interpretation']='Newly observed means absent from the pre-attach resident-page map, not proven newly reserved. API byte counts are not net commitment. Fixed address ranges do not prove reservation identity after reuse. Observer memory is included.'
        self.result['completed']=True;self.checkpoint('capture-complete')
        return dict(path=self.path.name,events=len(snapshot['events']),
                    instrumented=True,memory_acceptance=False)
