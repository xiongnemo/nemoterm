"""A newly focused session must never create an unintended solid system caret."""
from native_test_utils import (root,c,w,u,k,hashlib,json,os,sys,tempfile,Path,
    read_snapshot,write_snapshot,wait_for,find_window)
from owned_job import OwnedJob, k as job_api
from frida_test_utils import call_frida, detach_session
import frida
import atexit
import faulthandler
import time
import uuid
import winreg

exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
profile='caret-startup-'+uuid.uuid4().hex
keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),completed=False,
    instrumented=True,scope='Frida-spawned process assigned to an owned job before resume')
evidence_path=root/'research/caret-startup-observed.json'
# A native instrumentation stall must leave time for CI to upload its evidence.
# OwnedJob's kill-on-close handle also applies if this watchdog exits Python.
if os.environ.get('CI')=='true':
    faulthandler.dump_traceback_later(120,exit=True)
    atexit.register(faulthandler.cancel_dump_traceback_later)

def checkpoint(phase):
    evidence['phase']=phase
    evidence.setdefault('phases',[]).append(dict(name=phase,monotonic=time.monotonic()))
    write_snapshot(evidence_path,evidence)
    print('Startup caret:',phase,flush=True)

def observe_call(phase,function,*args):
    checkpoint(phase)
    return call_frida(phase,function,*args)

with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:
    for name,value in dict(WarnOnClose=0,NemoRenderer=0).items():
        winreg.SetValueEx(key,name,0,winreg.REG_DWORD,value)
try:
    with tempfile.TemporaryDirectory(prefix='nemoterm-caret-') as tmp,OwnedJob() as job:
        tmp=Path(tmp);report,control=tmp/'report',tmp/'control'
        device=frida.get_local_device();session=None;handle=None;assigned=False
        checkpoint('spawn')
        pid=device.spawn([str(exe),'-load',profile,'--cols','60','--rows','16','-e',
            sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control)],
            env=dict(os.environ,NEMOTERM_CONPTY='bundled'))
        try:
            evidence['pid']=pid
            checkpoint('assign-owned-job')
            handle=k.OpenProcess(0x101101,False,pid) # synchronize, query, set quota, terminate
            assert handle
            if not job_api.AssignProcessToJobObject(job.handle,handle):
                raise c.WinError(c.get_last_error())
            assigned=True
            session=observe_call('attach',device.attach,pid)
            script=observe_call('create-script',session.create_script,
                (root/'tests/caret_startup_probe.js').read_text(encoding='utf-8'))
            errors=[];script.on('message',lambda message,data:errors.append(message) if message['type']=='error' else None)
            observe_call('load-script',script.load)
            observe_call('resume',device.resume,pid)
            checkpoint('window-and-fixture-ready')
            hwnd=wait_for(lambda:find_window(pid));wait_for(lambda:read_snapshot(report))
            # This pinned Frida version does not cancel synchronous RPC waits;
            # the CI fixture watchdog covers these two observation requests.
            checkpoint('startup-events')
            evidence['startup']=script.exports_sync.events()
            # Exercise a normal focus event as well, without global input.
            checkpoint('send-focus')
            u.SendMessageW(hwnd,7,0,0)
            checkpoint('focus-events')
            evidence['after_focus']=script.exports_sync.events()
            assert evidence['after_focus'],evidence
            assert not errors,errors
            assert all(event['result'] and event['bitmap'] not in ('0x0','0x1')
                       for event in evidence['after_focus']),evidence
            # This probe observes startup/focus, not shutdown. Unload its hooks
            # while the frontend is alive, before asking that process to exit.
            assert k.WaitForSingleObject(handle,0)==258,'Frontend exited before observer cleanup'
            checkpoint('detach-live-observer')
            detach_session(session)
            session=None
            evidence['observer_detached_before_stop']=True
            checkpoint('stop-fixture')
            write_snapshot(control,dict(stop=True))
            checkpoint('wait-process-exit')
            assert k.WaitForSingleObject(handle,10000)==0
            exit_code=w.DWORD()
            assert job_api.GetExitCodeProcess(handle,c.byref(exit_code))
            evidence['process_exit_code']=exit_code.value
            assert exit_code.value==0,evidence
            checkpoint('drain-owned-job')
            evidence['owned_job_cleanup']=job.finish(grace=5)
            assert not evidence['owned_job_cleanup']['terminated_remaining']
        except BaseException as error:
            evidence.update(error=repr(error),failed_phase=evidence['phase'])
            write_snapshot(evidence_path,evidence)
            raise
        finally:
            try:
                if session and not session.is_detached:
                    checkpoint('cleanup-detach')
                    detach_session(session)
            finally:
                try:
                    if not assigned:observe_call('cleanup-spawn',device.kill,pid)
                    else:evidence.setdefault('owned_job_cleanup',job.finish(grace=0))
                finally:
                    if handle:k.CloseHandle(handle)
        evidence['completed']=True
        checkpoint('complete')
finally:
    if sys.exc_info()[0]:
        evidence['completed']=False
        evidence.setdefault('error',repr(sys.exc_info()[1]))
        evidence.setdefault('failed_phase',evidence.get('phase'))
    try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
    finally:write_snapshot(evidence_path,evidence)
print('Startup caret ownership passed:',len(evidence['startup']),'observed creation calls')
