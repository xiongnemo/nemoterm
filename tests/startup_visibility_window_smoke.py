"""Verify initial show state and later explicit VT/Win32 visibility requests."""
from native_test_utils import *
from owned_job import OwnedJob
import uuid,winreg

u.IsIconic.argtypes=[w.HWND]
u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
font='Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light'
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),completed=False,
    memory_acceptance=False,font=font,cases=[],checks=[])
def top_window(pid,kind):
    found=[]
    @c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
    def visit(hwnd,_):
        owner=w.DWORD();u.GetWindowThreadProcessId(hwnd,c.byref(owner))
        if owner.value==pid:
            name=c.create_unicode_buffer(128);u.GetClassNameW(hwnd,name,len(name))
            if name.value==kind:found.append(hwnd)
        return True
    u.EnumWindows(visit,0)
    return next(iter(found),None)
try:
    for tabbed in (False,True):
        for minimized in (False,True):
            profile='visibility-'+uuid.uuid4().hex;keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
            case=dict(tabbed=tabbed,minimized=minimized,operations=[]);evidence['cases'].append(case)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:
                for name,value in dict(WarnOnClose=0,CloseOnExit=1,NemoRenderer=0).items():
                    winreg.SetValueEx(key,name,0,winreg.REG_DWORD,value)
            try:
                with tempfile.TemporaryDirectory(prefix='nemoterm-visibility-') as tmp,OwnedJob() as job:
                    tmp=Path(tmp);startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW
                    startup.wShowWindow=7 if minimized else 1
                    process=job.spawn([str(exe),'-load',profile,*(['--tabs'] if tabbed else []),
                        '--cols','160','--rows','48','--font',font,'-e',
                        sys.executable,str(root/'tests/startup_visibility_fixture.py'),str(tmp)],
                        startupinfo=startup,creationflags=subprocess.CREATE_NO_WINDOW,
                        env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_UTF8_INPUT='1'))
                    try:
                        host=wait_for(lambda:top_window(process.pid,'NemotermHost' if tabbed else 'Nemoterm'))
                        report=wait_for(lambda:read_snapshot(tmp/'report.json'))
                        case['actual_grid']=[report['columns'],report['rows']]
                        case['initial_iconic']=bool(u.IsIconic(host));assert case['initial_iconic']==minimized,case
                        evidence['checks'].append(f'initial minimized={minimized}, tabs={tabbed}')
                        # Acknowledge every command through the actual ConPTY input path.
                        # Native calls act on this child's own console pseudo-window.
                        for phase,(operation,expected) in enumerate([
                            ('vt_restore',False),('vt_minimize',True),('vt_restore',False),
                            ('native_minimize',True),('native_restore',False)],1):
                            write_snapshot(tmp/'control.json',dict(phase=phase,operation=operation))
                            wait_snapshot(lambda:read_snapshot(tmp/'report.json'),lambda r:r.get('phase')==phase)
                            wait_for(lambda:bool(u.IsIconic(host))==expected)
                            case['operations'].append(dict(operation=operation,iconic=bool(u.IsIconic(host))))
                        evidence['checks'].append(f'explicit VT and Win32 visibility, minimized={minimized}, tabs={tabbed}')
                        write_snapshot(tmp/'control.json',dict(stop=True));process.wait(timeout=8)
                        case['cleanup']=job.finish(grace=5);assert not case['cleanup']['terminated_remaining']
                    finally:case.setdefault('cleanup',job.finish(grace=0))
            finally:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
    evidence['completed']=True
finally:
    failure=sys.exc_info()[1]
    if failure:evidence['error']=repr(failure)
    (root/'research/startup-visibility-observed.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
print('Startup visibility passed:',len(evidence['checks']),'groups')
