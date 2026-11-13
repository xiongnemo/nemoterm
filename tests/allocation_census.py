"""Explicit diagnostic observer for one fixture-owned frontend PID.

This changes the observed process. None of its memory readings are acceptance.
The controller must enforce a hard deadline around synchronous Frida RPC.
"""
import hashlib
import time
from pathlib import Path
import frida
from native_test_utils import c,w,k,mmap,memory_sample
from fixture_io import write_snapshot
from frida_test_utils import call_frida,detach_session
from working_set_regions import private_regions,private_page_addresses,reservation_range
from allocation_census_pages import correlate_pages

k.GetProcessId.argtypes,k.GetProcessId.restype=[w.HANDLE],w.DWORD


class AllocationCensus:
    def __init__(self,pid,handle,path):
        if k.GetProcessId(handle)!=pid:raise ValueError('Handle does not match owned PID')
        self.pid,self.handle,self.path=pid,handle,Path(path)
        self.session=self.script=None
        self.errors=[]
        self.result=dict(pid=pid,instrumented=True,memory_acceptance=False,completed=False,
                         observer_detached=False,snapshots_atomic=False)

    def checkpoint(self,phase):
        self.result['phase']=phase
        write_snapshot(self.path,self.result)
        print('Allocation census:',phase,flush=True)

    def start(self):
        self.checkpoint('select-pre-attach-reservations')
        before=private_regions(self.handle)
        candidates=[r for r in before['allocations'] if r['kind']=='private' and r['private_ws']>=65536]
        selected=candidates[:64]
        if not selected:raise RuntimeError('No sizeable pre-attach private reservations')
        ranges=[reservation_range(self.handle,int(r['allocation'],16)) for r in selected]
        self.result.update(before=before,scope=dict(pid=self.pid,ranges=ranges,capacity=65536),
            selection=dict(minimum_private_ws=65536,maximum_reservations=64,
                selected_reservations=len(selected),eligible_reservations=len(candidates),
                selected_private_ws=sum(r['private_ws'] for r in selected)))
        folder=Path(__file__).resolve().parent
        names=('allocation_census_probe.js','allocation_census.h','allocation_census_pages.py',
               'working_set_regions.py','allocation_census.py','tabs_window_smoke.py','tab_workload_memory.py')
        self.result['source_sha256']={name:hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in names}
        self.checkpoint('attach-owned-frontend')
        self.session=call_frida('allocation-attach',frida.attach,self.pid)
        self.script=call_frida('allocation-create',self.session.create_script,
                               (folder/names[0]).read_text(encoding='utf-8'))
        self.script.on('message',lambda message,data:self.errors.append(message)
                       if message['type']=='error' else None)
        call_frida('allocation-load',self.script.load)
        self.checkpoint('initialize-native-hooks')
        self.result['initial_counts']=self.script.exports_sync.initialize(
            self.result['scope'],(folder/names[1]).read_text(encoding='utf-8'))
        self.checkpoint('observe-workload')

    def freeze(self):
        self.checkpoint('freeze-live-blocks')
        started=time.monotonic()
        self.result['snapshot']=self.script.exports_sync.freeze()
        frozen=time.monotonic()
        self.checkpoint('map-private-resident-pages')
        pages=private_page_addresses(self.handle)
        sampled=time.monotonic()
        self.result.update(private_page_addresses=[hex(p) for p in pages],
            memory_after_freeze=memory_sample(self.handle),
            timing=dict(freeze_rpc_seconds=frozen-started,page_query_after_freeze_seconds=sampled-frozen),
            observer_errors=self.errors)
        snapshot=self.result['snapshot']
        if self.errors or not snapshot['valid'] or snapshot['counts']['active']:
            self.checkpoint('invalid-capture')
            raise RuntimeError('Native allocation capture is invalid')
        self.result['correlation']=correlate_pages(snapshot['entries'],pages,
                                                  self.result['scope']['ranges'],mmap.PAGESIZE)
        self.result['completed']=True
        self.checkpoint('capture-complete')
        return dict(path=self.path.name,counts=snapshot['counts'],
            observed_requested_bytes_on_private_pages=self.result['correlation']['observed_requested_bytes_on_private_pages'],
            instrumented=True,memory_acceptance=False)

    def close(self):
        if self.session is None:return
        self.checkpoint('detach-live-observer')
        try:
            if self.script is not None:
                call_frida('allocation-unload',self.script.unload)
        finally:
            detach_session(self.session)
            self.session=self.script=None
        self.result['observer_detached']=True
        self.checkpoint('observer-detached')
