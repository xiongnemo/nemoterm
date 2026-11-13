"""Record owned frontend metadata while dedicated CI records kernel ETW.

This class injects nothing. The workflow starts and stops its own WPR session.
It is diagnostic evidence, not normal working-set acceptance.
"""
import hashlib
import os
import time
from pathlib import Path
from native_test_utils import c,w,k,mmap,memory_sample
from fixture_io import write_snapshot
from working_set_regions import private_regions,private_page_addresses,reservation_range,reservation_layout

k.GetProcessId.argtypes,k.GetProcessId.restype=[w.HANDLE],w.DWORD


class EtwMemoryTrace:
    def __init__(self,pid,handle,path):
        if k.GetProcessId(handle)!=pid or os.environ.get('NEMOTERM_ETW_RECORDING')!='1':
            raise ValueError('Expected owned PID and dedicated workflow ETW recording')
        self.pid,self.handle,self.path=pid,handle,Path(path)
        self.result=dict(pid=pid,instrumented=False,injected=False,kernel_etw_recording=True,
            memory_acceptance=False,completed=False,snapshots_atomic=False)

    def checkpoint(self,phase):
        self.result['phase']=phase
        self.result.setdefault('stages',[]).append(dict(phase=phase,unix_ns=time.time_ns()))
        write_snapshot(self.path,self.result)
        print('ETW frontend metadata:',phase,flush=True)

    def start(self):
        self.checkpoint('before-workload')
        before=private_regions(self.handle)
        candidates=[r for r in before['allocations'] if r['kind']=='private' and r['private_ws']>=65536]
        selected=candidates[:64]
        ranges=[reservation_range(self.handle,int(r['allocation'],16)) for r in selected]
        if not ranges:raise RuntimeError('No selected private reservations')
        self.result.update(before=before,scope=dict(pid=self.pid,ranges=ranges),
            before_layouts=[reservation_layout(self.handle,r) for r in ranges],
            memory_before_workload=memory_sample(self.handle),
            selection=dict(minimum_private_ws=65536,maximum_reservations=64,
                selected_reservations=len(selected),eligible_reservations=len(candidates)))
        folder=Path(__file__).resolve().parent
        files=('etw_memory_trace.py','working_set_regions.py','tabs_window_smoke.py','tab_workload_memory.py')
        self.result['source_sha256']={name:hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in files}
        self.checkpoint('observe-workload')

    def freeze(self):
        self.checkpoint('after-workload')
        after_layouts=[reservation_layout(self.handle,r) for r in self.result['scope']['ranges']]
        pages=private_page_addresses(self.handle)
        before_private={e['allocation']:e['private_ws'] for e in self.result['before']['allocations']}
        changes=[]
        for before,after in zip(self.result['before_layouts'],after_layouts):
            start,end=int(before['start'],16),int(before['end'],16)
            changes.append(dict(start=before['start'],end=before['end'],reserved_bytes=end-start,
                before_committed_bytes=before['committed_bytes'],after_committed_bytes=after['committed_bytes'],
                before_private_ws=before_private.get(before['start'],0),
                after_private_ws=sum(start<=p<end for p in pages)*mmap.PAGESIZE))
        self.result.update(after_layouts=after_layouts,page_size=mmap.PAGESIZE,
            private_page_addresses=[hex(p) for p in pages],after=private_regions(self.handle),
            reservation_changes=changes,memory_after_workload=memory_sample(self.handle),completed=True)
        self.checkpoint('metadata-complete')
        return dict(path=self.path.name,pid=self.pid,injected=False,kernel_etw_recording=True,memory_acceptance=False)

    def close(self):
        # The workflow owns WPR; process cleanup must not stop a global session.
        self.checkpoint('metadata-closed')
