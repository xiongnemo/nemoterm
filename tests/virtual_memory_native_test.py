"""Validate scoped VM metadata and query layouts in an owned remote CI worker."""
import faulthandler
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import frida
from native_test_utils import c,w,k
from frida_test_utils import call_frida,detach_session
from owned_job import OwnedJob
from working_set_regions import reservation_layout

root=Path(__file__).resolve().parent.parent
path=root/'virtual-memory-native.json'
evidence=dict(completed=False,memory_acceptance=False,transitions=[])
faulthandler.dump_traceback_later(90,exit=True)


def checkpoint(phase):
    evidence['phase']=phase
    path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print('Virtual memory observer:',phase,flush=True)


try:
    with OwnedJob() as job:
        process=job.spawn([sys.executable,'-c','import time; time.sleep(120)'],
                          creationflags=subprocess.CREATE_NO_WINDOW)
        session=script=None;handle=None
        try:
            handle=k.OpenProcess(0x410,False,process.pid)
            if not handle:raise c.WinError()
            files=('virtual_memory_probe.js','virtual_memory_selftest.js','working_set_regions.py')
            evidence['source_sha256']={name:hashlib.sha256((root/'tests'/name).read_bytes()).hexdigest() for name in files}
            source='\n'.join((root/'tests'/name).read_text(encoding='utf-8') for name in files[:2])
            checkpoint('attach-owned-worker')
            session=call_frida('virtual-attach',frida.attach,process.pid)
            script=call_frida('virtual-create',session.create_script,source)
            errors=[]
            script.on('message',lambda message,data:errors.append(message) if message['type']=='error' else None)
            call_frida('virtual-load',script.load)
            scope=script.exports_sync.prepare(process.pid)
            evidence['scope']=scope
            initial=reservation_layout(handle,scope['ranges'][0])
            assert initial['committed_bytes']==0
            evidence['initial_layout']=initial
            evidence['initialized']=script.exports_sync.initialize(scope)
            for name,expected_commit in (('commit',8192),('excluded',8192),('failed',8192),
                                         ('decommit',4096),('extended',8192),('release',0)):
                checkpoint(name)
                result=script.exports_sync.transition(name)
                layout=reservation_layout(handle,scope['ranges'][0])
                evidence['transitions'].append(dict(result=result,layout=layout))
                assert (result['status']<0)==(name=='failed'),result
                assert layout['committed_bytes']==expected_commit,layout
            checkpoint('freeze')
            snapshot=script.exports_sync.freeze();evidence['snapshot']=snapshot
            assert snapshot['valid'] and not snapshot['active'] and not errors,snapshot
            events=snapshot['events']
            assert len(events)==5,events
            assert [e['success'] for e in events]==[True,False,True,True,True]
            assert [e['api'] for e in events]==['NtAllocateVirtualMemory','NtAllocateVirtualMemory',
                'NtFreeVirtualMemory','NtAllocateVirtualMemoryEx','NtFreeVirtualMemory']
            assert [e['flags'] for e in events]==[0x1000,0x1000,0x4000,0x1000,0x8000]
            assert [e['requested_bytes'] for e in events]==['8192','4096','4096','4096','0']
            assert all(e['stack'] and e['caller']['module'] for e in events)
            assert snapshot['ignored_out_of_scope']>0
            assert events[0]['address']==hex(int(scope['ranges'][0]['start'],16)+4096)
            assert events[3]['address']==hex(int(scope['ranges'][0]['start'],16)+12288)
            assert events[4]['address']==scope['ranges'][0]['start']
            assert all(r['state']==0x10000 for r in evidence['transitions'][-1]['layout']['regions'])
            checkpoint('cleanup-reservations')
            script.exports_sync.cleanup()
            call_frida('virtual-unload',script.unload);script=None
            detach_session(session);session=None
        finally:
            try:
                if session:detach_session(session)
            finally:
                if handle:k.CloseHandle(handle)
                evidence['cleanup']=job.finish(grace=0)
                process.wait(timeout=5)
        evidence['completed']=True;checkpoint('complete')
finally:
    if sys.exc_info()[0]:evidence.update(completed=False,error=repr(sys.exc_info()[1]))
    path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    faulthandler.cancel_dump_traceback_later()
