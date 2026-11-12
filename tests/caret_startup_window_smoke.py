"""A newly focused session must never create an unintended solid system caret."""
from native_test_utils import (root,c,w,u,k,hashlib,json,os,sys,tempfile,Path,
    read_snapshot,write_snapshot,wait_for,find_window)
from owned_job import OwnedJob, k as job_api
import frida
import uuid
import winreg

exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
profile='caret-startup-'+uuid.uuid4().hex
keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),completed=False,
    instrumented=True,scope='Frida-spawned process assigned to an owned job before resume')
with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:
    for name,value in dict(WarnOnClose=0,NemoRenderer=0).items():
        winreg.SetValueEx(key,name,0,winreg.REG_DWORD,value)
try:
    with tempfile.TemporaryDirectory(prefix='nemoterm-caret-') as tmp,OwnedJob() as job:
        tmp=Path(tmp);report,control=tmp/'report',tmp/'control'
        device=frida.get_local_device();session=None;handle=None;assigned=False
        pid=device.spawn([str(exe),'-load',profile,'--cols','60','--rows','16','-e',
            sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control)],
            env=dict(os.environ,NEMOTERM_CONPTY='bundled'))
        try:
            handle=k.OpenProcess(0x101101,False,pid) # synchronize, query, set quota, terminate
            assert handle
            if not job_api.AssignProcessToJobObject(job.handle,handle):
                raise c.WinError(c.get_last_error())
            assigned=True
            session=device.attach(pid)
            script=session.create_script((root/'tests/caret_startup_probe.js').read_text())
            errors=[];script.on('message',lambda message,data:errors.append(message) if message['type']=='error' else None)
            script.load();device.resume(pid)
            hwnd=wait_for(lambda:find_window(pid));wait_for(lambda:read_snapshot(report))
            evidence['startup']=script.exports_sync.events()
            # Exercise a normal focus event as well, without global input.
            u.SendMessageW(hwnd,7,0,0)
            evidence['after_focus']=script.exports_sync.events()
            assert evidence['after_focus'],evidence
            assert not errors,errors
            assert all(event['result'] and event['bitmap'] not in ('0x0','0x1')
                       for event in evidence['after_focus']),evidence
            write_snapshot(control,dict(stop=True))
            assert k.WaitForSingleObject(handle,10000)==0
            evidence['owned_job_cleanup']=job.finish(grace=5)
            assert not evidence['owned_job_cleanup']['terminated_remaining']
            evidence['completed']=True
        finally:
            if session:
                try:session.detach()
                except frida.InvalidOperationError:pass
            if not assigned:device.kill(pid)
            else:evidence.setdefault('owned_job_cleanup',job.finish(grace=0))
            if handle:k.CloseHandle(handle)
finally:
    if sys.exc_info()[0]:evidence['error']=repr(sys.exc_info()[1])
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
    (root/'research/caret-startup-observed.json').write_text(json.dumps(evidence,indent=2))
print('Startup caret ownership passed:',len(evidence['startup']),'observed creation calls')
