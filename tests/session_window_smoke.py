"""Session ownership before tab hosting: independent I/O, exit, failure and reuse.

The temporary frontend still uses separate windows in one process. Tests target
owned HWNDs; this is session-core evidence, not four-sided tab UI acceptance.
"""
from native_test_utils import (root,c,w,u,k,hashlib,json,os,subprocess,sys,tempfile,
    Path,time,read_snapshot,write_snapshot,wait_snapshot,wait_for,memory_sample)
from owned_job import OwnedJob
import argparse
import frida
import uuid
import winreg

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--renderer',choices=('gdi','opengl','directx'),default='gdi')
args=parser.parse_args()
exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
profile='session-core-'+uuid.uuid4().hex
keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
u.GetGuiResources.argtypes,u.GetGuiResources.restype=[w.HANDLE,w.DWORD],w.DWORD
u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
u.IsWindow.argtypes=[w.HWND]
k.GetProcessHandleCount.argtypes=[w.HANDLE,c.POINTER(w.DWORD)]
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    renderer=args.renderer,completed=False,checks=[],resources=[],memory_instrumented=False)

def windows(pid):
    found=[]
    @c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
    def visit(hwnd,_):
        owner=w.DWORD();name=c.create_unicode_buffer(128)
        u.GetWindowThreadProcessId(hwnd,c.byref(owner));u.GetClassNameW(hwnd,name,128)
        if owner.value==pid and name.value=='Nemoterm' and u.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True
    u.EnumWindows(visit,0)
    return found

with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:
    for name,value in dict(WarnOnClose=0,CloseOnExit=1,NemoRenderer=
            {'gdi':0,'opengl':1,'directx':2}[args.renderer]).items():
        winreg.SetValueEx(key,name,0,winreg.REG_DWORD,value)
try:
    with tempfile.TemporaryDirectory(prefix='nemoterm-sessions-') as tmp,OwnedJob() as job:
        tmp=Path(tmp);known=set();children=[];serial=0;instrument=None
        process=job.spawn([str(exe),'-load',profile,'--cols','60','--rows','16','-e',
            sys.executable,str(root/'tests/session_fixture.py'),str(tmp)],
            env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_UTF8_INPUT='1'),
            creationflags=subprocess.CREATE_NO_WINDOW)
        handle=k.OpenProcess(0x410,False,process.pid)
        assert handle
        def new_child(before):
            def ready():
                for path in tmp.glob('*.launch.json'):
                    v=read_snapshot(path)
                    if v and v['pid'] not in known:return v
            child=wait_for(ready,timeout=15);known.add(child['pid'])
            def new_window():
                values=set(windows(process.pid))-set(before)
                return next(iter(values)) if len(values)==1 else None
            child['hwnd']=wait_for(new_window)
            assert child['parent']==process.pid,child
            child['report']=tmp/f"{child['pid']}.report.json"
            child['control']=tmp/f"{child['pid']}.control.json"
            wait_for(lambda:read_snapshot(child['report']))
            child['session']=int(u.GetPropW(child['hwnd'],'NemotermSessionId') or 0)
            assert child['session'] and all(ch['session']!=child['session'] for ch in children)
            child['renderer']=int(u.GetPropW(child['hwnd'],'NemotermRenderer') or 0)
            if args.renderer=='directx' and os.environ.get('NEMOTERM_REQUIRE_DIRECTX')=='1':
                assert child['renderer']==3,child
            children.append(child)
            return child
        def output(child,extra=''):
            global serial
            serial+=1
            write_snapshot(child['control'],dict(phase=serial,sequence=
                '\x1b[?25l\x1b[2J\x1b[H'+f"SESSION {child['pid']} {serial}"+extra+'\x1b[5n'))
            return wait_snapshot(lambda:read_snapshot(child['report']),
                lambda v:v.get('phase')==serial and '\x1b[0n'.encode().hex() in v.get('hex',''))
        def barrier(child):
            global serial
            serial+=1
            request=read_snapshot(child['control']);request['input_barrier']=serial
            write_snapshot(child['control'],request)
            return wait_snapshot(lambda:read_snapshot(child['report']),lambda v:v.get('input_barrier')==serial)
        def duplicate(child):
            before=windows(process.pid)
            u.SendMessageW(child['hwnd'],0x111,0x30,0)
            result=new_child(before);output(result)
            return result
        def close(child,via_child):
            if via_child:write_snapshot(child['control'],dict(stop=True))
            else:u.PostMessageW(child['hwnd'],0x10,0,0)
            wait_for(lambda:not u.IsWindow(child['hwnd']),timeout=15)
        def resources():
            count=w.DWORD();assert k.GetProcessHandleCount(handle,c.byref(count))
            return dict(handles=count.value,gdi=u.GetGuiResources(handle,0),
                user=u.GetGuiResources(handle,1),**memory_sample(handle))
        try:
            first=new_child([]);output(first)
            second=duplicate(first);third=duplicate(second)
            for child in (first,second,third):
                output(child)
                token=f"session-{child['pid']};"
                for ch in token:u.SendMessageW(child['hwnd'],0x102,ord(ch),1)
                current=barrier(child)
                assert token.encode().hex() in current['hex'],current
                for other in (first,second,third):
                    if other is not child:
                        assert token.encode().hex() not in barrier(other)['hex']
            evidence['checks'].append('three sessions route input/output independently in one process')
            close(second,True);assert process.poll() is None;output(first);output(third)
            close(first,False);assert process.poll() is None;output(third)
            wait_for(lambda:job.accounting()['active']==3)
            evidence['checks'].append('middle child exit and original window close preserve remaining session')
            baseline=resources();evidence['baseline']=baseline
            for index in range(12):
                child=duplicate(third)
                # Free a synchronized snapshot, image storage, and pending
                # terminal/window callbacks while another shell stays live.
                output(child,'\r\n\x1bP0;1q"1;1;48;12#1;2;80;20;50#1!48~-!48~\x1b\\')
                write_snapshot(child['control'],dict(phase='frozen',sequence='\x1b[?2026hFROZEN'))
                wait_snapshot(lambda:read_snapshot(child['report']),lambda v:v.get('phase')=='frozen')
                close(child,index%2==0);output(third)
                wait_for(lambda:job.accounting()['active']==3)
                value=resources();evidence['resources'].append(value)
                assert value['handles']<=baseline['handles']+6,(baseline,value)
                assert value['gdi']<=baseline['gdi']+2,(baseline,value)
                assert value['user']<=baseline['user']+2,(baseline,value)
            evidence['checks'].append('12 image/synchronized-output open/close cycles release handles')
            # Memory samples above are all from the uninjected frontend.
            instrument=frida.attach(process.pid)
            script=instrument.create_script((root/'tests/session_faults.js').read_text())
            errors=[];script.on('message',lambda message,data:errors.append(message) if message['type']=='error' else None)
            script.load();before=set(windows(process.pid));script.exports_sync.arm('process')
            u.SendMessageW(third['hwnd'],0x111,0x30,0)
            status=script.exports_sync.status();evidence['startup_fault']=status
            assert status['hits'] and status['hits'][0]=={'event':'create-failure','result':0},status
            assert len(status['hits'])==2 and status['hits'][1]['event']=='start-error',status
            assert set(windows(process.pid))==before and process.poll() is None
            output(third);recovered=duplicate(third)
            evidence['checks'].append('failed shell start leaves existing session alive and permits retry')
            script.exports_sync.arm('window')
            before=set(windows(process.pid))
            u.SendMessageW(third['hwnd'],0x111,0x30,0)
            status=script.exports_sync.status();evidence['window_fault']=status
            assert status['hits'][-2]=={'event':'window-failure','result':'0x0'},status
            assert status['hits'][-1]['event']=='start-error',status
            assert set(windows(process.pid))==before and process.poll() is None
            output(third);output(recovered)
            evidence['checks'].append('window creation failure frees a partial seat and preserves both running sessions')
            output(recovered)
            script.exports_sync.paste(hex(recovered['hwnd']),hex(third['session']),'STALE-PASTE')
            assert b'STALE-PASTE'.hex() not in barrier(recovered)['hex']
            script.exports_sync.paste(hex(recovered['hwnd']),hex(recovered['session']),'VALID-PASTE')
            assert b'VALID-PASTE'.hex() in barrier(recovered)['hex']
            assert b'VALID-PASTE'.hex() not in barrier(third)['hex']
            assert not errors,errors
            evidence['checks'].append('synthetic delayed paste rejects another session identity; valid paste stays isolated')
            close(recovered,False);output(third)
            instrument.detach();instrument=None
            close(third,True);assert process.wait(timeout=15)==0
            evidence['owned_job_cleanup']=job.finish(grace=5)
            assert not evidence['owned_job_cleanup']['terminated_remaining']
            evidence['checks'].append('last session exit drains all owned processes naturally')
            evidence['completed']=True
        finally:
            evidence['frontend_exit']=process.poll()
            evidence['children']=[{key:value for key,value in ch.items() if key not in ('report','control')} for ch in children]
            if instrument:
                try:instrument.detach()
                except frida.InvalidOperationError:pass
            k.CloseHandle(handle)
            evidence.setdefault('owned_job_cleanup',job.finish(grace=0))
finally:
    if sys.exc_info()[0]:evidence['error']=repr(sys.exc_info()[1])
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
    (root/'research'/f'session-window-{args.renderer}-observed.json').write_text(json.dumps(evidence,indent=2))
print('Session core passed:',args.renderer,len(evidence['checks']),'checks')
