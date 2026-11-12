"""Owned Direct2D factory/device failure, recovery and resource lifetime."""
from native_test_utils import *
from owned_job import OwnedJob
from gpu_capture import OwnedGPUCapture
import frida
import uuid
import winreg

exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
u.GetGuiResources.argtypes,u.GetGuiResources.restype=[w.HANDLE,w.DWORD],w.DWORD
u.SendMessageTimeoutW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM,w.UINT,w.UINT,c.POINTER(c.c_size_t)]
k.GetProcessHandleCount.argtypes=[w.HANDLE,c.POINTER(w.DWORD)]
profile='gpu-lifecycle-'+uuid.uuid4().hex
keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),checks=[],completed=False,
              memory_instrumented=True,input_scope='owned HWND and COM HRESULT injection')
started=time.monotonic()
with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:
    for name,value in dict(NemoRenderer=0,WarnOnClose=0,LockSize=0).items():
        winreg.SetValueEx(key,name,0,winreg.REG_DWORD,value)
try:
    with tempfile.TemporaryDirectory(prefix='nemoterm-gpu-lifecycle-') as tmp,OwnedJob() as job:
        tmp=Path(tmp);report=tmp/'report';control=tmp/'control';ui_report=tmp/'ui-report';ui_control=tmp/'ui-control'
        process=job.spawn([str(exe),'-load',profile,'--cols','80','--rows','24','-e',sys.executable,
            str(root/'tests/mouse_fixture.py'),str(report),str(control),'300'],
            env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
        handle=k.OpenProcess(0x410,False,process.pid);session=None;script=None;gpu=None
        try:
            hwnd=wait_for(lambda:find_window(process.pid));wait_for(lambda:read_snapshot(report))
            driver=job.spawn(['powershell.exe','-NoProfile','-File',str(root/'tests/gpu_settings_driver.ps1'),
                '-TargetProcess',str(process.pid),'-TargetWindow',str(hwnd),'-Control',str(ui_control),'-Report',str(ui_report)],
                creationflags=subprocess.CREATE_NO_WINDOW)
            wait_snapshot(lambda:read_snapshot(ui_report),lambda v:v.get('ready'),timeout=20)
            session=frida.attach(process.pid)
            script=session.create_script('const ownedWindow=ptr("'+hex(hwnd)+'");\n'+(root/'tests/gpu_faults.js').read_text())
            errors=[];script.on('message',lambda message,data:errors.append(message) if message.get('type')=='error' else None)
            script.load();serial=0
            def active():return int(u.GetPropW(hwnd,'NemotermRenderer') or 0)
            def mode(value):
                global serial
                serial+=1;write_snapshot(ui_control,dict(id=serial,mode=value))
                def received():
                    r=read_snapshot(ui_report)
                    if r.get('error'):raise AssertionError(r)
                    return r
                wait_snapshot(received,lambda v:v.get('id')==serial,timeout=30)
                # Closing the modal dialog precedes the parent's reconfigure
                # callback. Wait for that owned UI thread to finish applying.
                result=c.c_size_t()
                assert u.SendMessageTimeoutW(hwnd,0,0,0,2,10000,c.byref(result))
                assert not errors,errors
                evidence.setdefault('mode_changes',[]).append(dict(requested=value,active=active(),faults=script.exports_sync.status()))
                return active()
            def output(name,colour=(27,191,103)):
                sequence='\x1b[?25l\x1b[0m\x1b[2J\x1b[H\x1b[48;2;'+(';'.join(map(str,colour)))+'m  \x1b[0m\x1b[5n'
                write_snapshot(control,dict(phase=name,sequence=sequence))
                reply=wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('phase')==name and bytes.fromhex(v.get('hex','')).endswith(b'\x1b[0n'))
                evidence.setdefault('output_replies',[]).append(dict(elapsed=time.monotonic()-started,**reply))
            def fault(name):
                status=script.exports_sync.status()
                assert len(status['hits'])==1 and status['hits'][0]['fault']==name,(name,status,errors)
                assert not errors,errors
                evidence['checks'].append(dict(fault=name,status=status,renderer=active()))
            def gdi_pixels():
                wait_for(lambda:capture(hwnd,return_pixels=True).count(bytes((27,191,103)))>=10)
            script.exports_sync.arm('factory')
            assert mode(2)==1
            fault('factory');output('factory-recovery');gdi_pixels()
            mode(0);script.exports_sync.arm('');hardware=mode(2)==3
            evidence['hardware_directx']=hardware
            if os.environ.get('NEMOTERM_REQUIRE_DIRECTX')=='1':assert hardware,'DirectX unavailable'
            if hardware:
                for name in ('draw','resize'):
                    script.exports_sync.arm(name)
                    if name=='draw':output('draw-failure')
                    else:
                        r=w.RECT();assert u.GetWindowRect(hwnd,c.byref(r))
                        assert u.MoveWindow(hwnd,r.left,r.top,r.right-r.left+80,r.bottom-r.top+40,True)
                    wait_for(lambda:active()==1);fault(name)
                    output(name+'-recovery');gdi_pixels()
                    mode(0);assert mode(2)==3
                def resources():
                    handles=w.DWORD();assert k.GetProcessHandleCount(handle,c.byref(handles))
                    return dict(gdi=u.GetGuiResources(handle,0),user=u.GetGuiResources(handle,1),handles=handles.value)
                baseline=resources();samples=[]
                for index in range(4):
                    assert mode(0)==1;assert mode(2)==3
                    output('cycle-'+str(index));samples.append(resources())
                for value in samples:
                    assert value['gdi']<=baseline['gdi']+4,(baseline,samples)
                    assert value['user']<=baseline['user']+4,(baseline,samples)
                    assert value['handles']<=baseline['handles']+8,(baseline,samples)
                evidence['resources']=dict(baseline=baseline,samples=samples)
                gpu=OwnedGPUCapture(process.pid,hwnd)
                wait_for(lambda:gpu.capture(return_pixels=True).count(bytes((27,191,103)))>=10)
                gpu.capture('gpu-lifecycle-directx.png')
                assert active()==3
            else:evidence['skipped']=['device EndDraw and Resize injection','hardware switch/resource cycles']
            write_snapshot(ui_control,dict(stop=True));assert driver.wait(timeout=10)==0
            write_snapshot(control,dict(stop=True));assert process.wait(timeout=10)==0
            evidence['completed']=True
        finally:
            evidence['elapsed_seconds']=time.monotonic()-started
            evidence['last_child_snapshot']=read_snapshot(report)
            evidence['last_ui_snapshot']=read_snapshot(ui_report)
            evidence['frontend_exit']=process.poll()
            if script and process.poll() is None:
                evidence['last_fault_status']=script.exports_sync.status()
                evidence['instrumentation_errors']=errors
            if gpu:gpu.close()
            if session:session.detach()
            k.CloseHandle(handle)
            evidence['owned_job_cleanup']=job.finish(grace=0)
finally:
    if sys.exc_info()[0]:evidence['error']=repr(sys.exc_info()[1])
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
    (root/'research/gpu-lifecycle-observed.json').write_text(json.dumps(evidence,indent=2))
print('Owned GPU failure and lifetime passed:',evidence)
