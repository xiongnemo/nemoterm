"""Default character grid and actual-font work-area clamp before shell launch."""
from native_test_utils import *
import uuid,winreg
exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
class MonitorInfo(c.Structure):
    _fields_=[('size',w.DWORD),('monitor',w.RECT),('work',w.RECT),('flags',w.DWORD)]
u.MonitorFromWindow.argtypes=[w.HWND,w.DWORD];u.MonitorFromWindow.restype=w.HANDLE
u.GetMonitorInfoW.argtypes=[w.HANDLE,c.POINTER(MonitorInfo)]
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),checks=[])
with tempfile.TemporaryDirectory(prefix='nemoterm-size-') as tmp:
    for oversized in (False,True):
        profile='size-test-'+uuid.uuid4().hex;path='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,path) as key:winreg.SetValueEx(key,'WarnOnClose',0,winreg.REG_DWORD,0)
        report,control=(Path(tmp)/(str(oversized)+n) for n in ('report','control'))
        args=['--cols','1000','--rows','1000','--font-size','24'] if oversized else []
        process=subprocess.Popen([str(exe),'-load',profile,*args,'-e',sys.executable,
            str(root/'tests/mouse_fixture.py'),str(report),str(control)],
            env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            hwnd=wait_for(lambda:find_window(process.pid));value=wait_for(lambda:read_snapshot(report))
            outer,client=w.RECT(),w.RECT();u.GetWindowRect(hwnd,c.byref(outer));u.GetClientRect(hwnd,c.byref(client))
            info=MonitorInfo();info.size=c.sizeof(info);assert u.GetMonitorInfoW(u.MonitorFromWindow(hwnd,2),c.byref(info))
            cols,rows=value['columns'],value['rows'];cw,ch=(client.right-2)//cols,(client.bottom-2)//rows
            maxcols=(info.work.right-info.work.left-(outer.right-outer.left-client.right+2))//cw
            maxrows=(info.work.bottom-info.work.top-(outer.bottom-outer.top-client.bottom+2))//ch
            assert (cols,rows)==(min(1000 if oversized else 160,maxcols),min(1000 if oversized else 48,maxrows)),(cols,rows,maxcols,maxrows)
            assert outer.left>=info.work.left and outer.top>=info.work.top and outer.right<=info.work.right and outer.bottom<=info.work.bottom
            handle=k.OpenProcess(0x410,False,process.pid)
            try:
                memory=memory_sample(handle)
                counters=Counters();counters.cb=c.sizeof(counters)
                assert ps.GetProcessMemoryInfo(handle,c.byref(counters),counters.cb)
                memory['peak_total_ws']=counters.peak_ws
            finally:k.CloseHandle(handle)
            assert memory['private_ws']<20_000_000 and memory['peak_total_ws']<50_000_000,memory
            evidence['checks'].append(dict(oversized=oversized,columns=cols,rows=rows,cell=[cw,ch],memory=memory,workarea=[info.work.left,info.work.top,info.work.right,info.work.bottom]))
        finally:
            write_snapshot(control,dict(stop=True))
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,path)
(root/'research/startup-size-observed.json').write_text(json.dumps(evidence,indent=2))
print('160x48 default and oversized startup work-area clamp passed:',evidence['checks'])
