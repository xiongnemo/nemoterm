"""Restart an inactive owned session without recycling stale paste delivery."""
from native_test_utils import (root,c,w,u,k,hashlib,json,os,subprocess,sys,tempfile,
    Path,read_snapshot,write_snapshot,wait_snapshot,wait_for,find_window,find_windows)
from owned_job import OwnedJob
import frida
import uuid
import winreg

exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
profile='session-restart-'+uuid.uuid4().hex
keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
u.GetSystemMenu.argtypes,u.GetSystemMenu.restype=[w.HWND,w.BOOL],w.HMENU
u.GetMenuState.argtypes,u.GetMenuState.restype=[w.HMENU,w.UINT,w.UINT],w.UINT
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    completed=False,cycles=[],instrumented=True,clipboard='synthetic request; real clipboard untouched')
with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:
    for name,value in dict(WarnOnClose=0,CloseOnExit=0,NemoRenderer=0).items():
        winreg.SetValueEx(key,name,0,winreg.REG_DWORD,value)
try:
    with tempfile.TemporaryDirectory(prefix='nemoterm-restart-') as tmp,OwnedJob() as job:
        tmp=Path(tmp);seen=set();session=None;serial=0
        process=job.spawn([str(exe),'-load',profile,'--cols','60','--rows','16','-e',
            sys.executable,str(root/'tests/session_fixture.py'),str(tmp)],
            env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
        def child(hwnd):
            def ready():
                for path in tmp.glob('*.launch.json'):
                    value=read_snapshot(path)
                    if value and value['pid'] not in seen:return value
            ch=wait_for(ready,timeout=15);seen.add(ch['pid'])
            assert ch['parent']==process.pid
            ch.update(hwnd=hwnd,report=tmp/f"{ch['pid']}.report.json",control=tmp/f"{ch['pid']}.control.json",
                identity=int(u.GetPropW(hwnd,'NemotermSessionId') or 0))
            wait_for(lambda:read_snapshot(ch['report']))
            return ch
        def output(ch,token):
            global serial
            serial+=1
            write_snapshot(ch['control'],dict(phase=serial,sequence=token+'\x1b[5n'))
            return wait_snapshot(lambda:read_snapshot(ch['report']),
                lambda v:v.get('phase')==serial and v.get('hex')=='1b5b306e')
        def barrier(ch):
            global serial
            serial+=1;request=read_snapshot(ch['control']);request['input_barrier']=serial
            write_snapshot(ch['control'],request)
            return wait_snapshot(lambda:read_snapshot(ch['report']),lambda v:v.get('input_barrier')==serial)
        try:
            hwnd=wait_for(lambda:find_window(process.pid));original=child(hwnd);output(original,'ORIGINAL')
            before=set(find_windows(process.pid));u.SendMessageW(hwnd,0x111,0x30,0)
            other_hwnd=wait_for(lambda:next(iter(set(find_windows(process.pid))-before),None))
            other=child(other_hwnd);output(other,'OTHER')
            session=frida.attach(process.pid)
            script=session.create_script((root/'tests/session_faults.js').read_text())
            errors=[];script.on('message',lambda message,data:errors.append(message) if message['type']=='error' else None)
            script.load();script.exports_sync.inactive_dialogs()
            for index in range(4):
                old_identity=original['identity'];old_pid=original['pid']
                write_snapshot(original['control'],dict(stop=True))
                menu=u.GetSystemMenu(hwnd,False)
                wait_for(lambda:u.GetMenuState(menu,0x40,0)!=0xffffffff,timeout=15)
                assert u.IsWindow(hwnd) and u.IsWindow(other_hwnd) and process.poll() is None
                output(other,'ACTIVE-WHILE-OTHER-INACTIVE')
                script.exports_sync.paste(hex(hwnd),hex(old_identity),'DISCONNECTED')
                u.SendMessageW(hwnd,0x111,0x40,0)
                original=child(hwnd)
                assert original['identity'] and original['identity']!=old_identity
                assert original['pid']!=old_pid
                output(original,'RESTARTED')
                script.exports_sync.paste(hex(hwnd),hex(old_identity),'OLD-SHELL')
                assert b'OLD-SHELL'.hex() not in barrier(original)['hex']
                script.exports_sync.paste(hex(hwnd),hex(original['identity']),'NEW-SHELL')
                assert b'NEW-SHELL'.hex() in barrier(original)['hex']
                assert b'NEW-SHELL'.hex() not in barrier(other)['hex']
                evidence['cycles'].append(dict(index=index,old_session=old_identity,
                    new_session=original['identity'],old_pid=old_pid,new_pid=original['pid']))
            evidence['instrumentation']=script.exports_sync.status()
            assert len(evidence['instrumentation']['hits'])==4 and not errors
            u.PostMessageW(hwnd,0x10,0,0);wait_for(lambda:not u.IsWindow(hwnd))
            output(other,'STILL-RUNNING-AFTER-RESTARTED-SEAT-CLOSE')
            session.detach();session=None
            u.PostMessageW(other_hwnd,0x10,0,0);assert process.wait(timeout=15)==0
            evidence['owned_job_cleanup']=job.finish(grace=5)
            assert not evidence['owned_job_cleanup']['terminated_remaining']
            evidence['completed']=True
        finally:
            if session:
                try:session.detach()
                except frida.InvalidOperationError:pass
            evidence['frontend_exit']=process.poll()
            evidence.setdefault('owned_job_cleanup',job.finish(grace=0))
finally:
    if sys.exc_info()[0]:evidence['error']=repr(sys.exc_info()[1])
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
    (root/'research/session-restart-observed.json').write_text(json.dumps(evidence,indent=2))
print('Session restart and paste isolation passed:',len(evidence['cycles']),'cycles')
