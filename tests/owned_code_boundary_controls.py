"""Owned positive and negative controls for the read-only code observer."""
import argparse
import ctypes as c
from ctypes import wintypes as w
import json
from pathlib import Path
import subprocess
import time
import uuid
import frida
from owned_job import OwnedJob
from owned_code_boundary import OwnedCodeBoundary

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--control',type=Path,required=True)
p.add_argument('--destination',type=Path,required=True)
args=p.parse_args()
args.destination.mkdir(parents=True,exist_ok=False)
k=c.WinDLL('kernel32',use_last_error=True)
k.CreateEventW.argtypes=[c.c_void_p,w.BOOL,w.BOOL,w.LPCWSTR];k.CreateEventW.restype=w.HANDLE
k.SetEvent.argtypes=[w.HANDLE];k.CloseHandle.argtypes=[w.HANDLE]
k.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];k.WaitForSingleObject.restype=w.DWORD
token='Local\\NemotermCodeBoundaryControl-'+str(uuid.uuid4())
go=k.CreateEventW(None,True,False,token)
if not go:raise c.WinError(c.get_last_error())
ready=k.CreateEventW(None,True,False,token+'-ready')
if not ready:
    k.CloseHandle(go)
    raise c.WinError(c.get_last_error())
result=dict(frida=frida.__version__,passed=False,snapshots=[])
session=None
try:
    with OwnedJob() as job,OwnedJob() as unrelated:
        process=job.spawn([str(args.control.resolve()),token,'normal',token+'-ready'],
                          creationflags=subprocess.CREATE_NO_WINDOW)
        assert k.WaitForSingleObject(ready,10000)==0, 'Control did not reach ready event'
        observer=OwnedCodeBoundary(process,job)
        result['baseline']=observer.identity
        try:OwnedCodeBoundary(process,unrelated)
        except RuntimeError as error:result['foreign_job_rejected']=str(error)
        else:raise AssertionError('Unrelated job accepted')
        result['snapshots'].append(observer.snapshot('before-attach'))
        assert not result['snapshots'][-1]['changed_blocks']
        session=frida.attach(process.pid)
        script=session.create_script("""
            Interceptor.attach(Process.getModuleByName('kernelbase.dll')
                .getExportByName('GetTickCount64'), {onEnter() {}});
        """)
        script.load()
        result['snapshots'].append(observer.snapshot('after-load'))
        assert any(r['module'].lower()=='kernelbase.dll'
                   for r in result['snapshots'][-1]['changes'])
        script.unload()
        session.detach();session=None
        result['snapshots'].append(observer.snapshot('after-detach'))
        assert all(s['matches_baseline'] for s in result['snapshots'][-1]['sections']
                   if s['module'].lower()=='kernelbase.dll')
        # Session detachment is not assumed to synchronously unload the agent.
        # Observe bounded intervals; retained runtime hooks are diagnostic data.
        for delay in (.01,.05,.2,1):
            time.sleep(delay)
            result['snapshots'].append(observer.snapshot('after-wait-'+str(delay)))
        assert all('observation_error' not in row for row in result['snapshots'])
        if not k.SetEvent(go):raise c.WinError(c.get_last_error())
        process.wait(timeout=15)
        result['process_exit']=process.returncode
        assert process.returncode==23
        result['after_exit']=observer.snapshot('after-exit')
        assert result['after_exit']['exit_code']==23 and not result['after_exit']['sections']
        result['cleanup']=job.finish(grace=2)
        assert not result['cleanup']['terminated_remaining']
        result['passed']=True
finally:
    if session:session.detach()
    k.CloseHandle(go);k.CloseHandle(ready)
    if 'job' in globals():result['cleanup']=job.cleanup
    (args.destination/'results.json').write_text(json.dumps(result,indent=2)+'\n')
print('Owned code-boundary controls passed',flush=True)
