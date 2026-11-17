"""Language persistence and Unicode UI acceptance on a disposable hosted desktop."""
import os
if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
    raise SystemExit('Run this test on a disposable GitHub-hosted Windows runner')
import ctypes as c
c.windll.user32.SetProcessDpiAwarenessContext(c.c_void_p(-4))
from native_test_utils import *
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile
from contextlib import contextmanager
import argparse, winreg

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--settings-helper',required=True,type=Path)
args=parser.parse_args()
exe=Path(os.environ['NEMOTERM_TEST_EXE']).resolve()
helper=args.settings_helper.resolve()
u.GetDpiForWindow.argtypes=[w.HWND];u.GetDpiForWindow.restype=w.UINT
u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
u.GetClassNameW.argtypes=[w.HWND,w.LPWSTR,c.c_int]
u.GetWindowTextW.argtypes=[w.HWND,w.LPWSTR,c.c_int]
u.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]
u.IsWindowEnabled.argtypes=[w.HWND]
ENUM=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
u.EnumWindows.argtypes=[ENUM,w.LPARAM]
ROOT_KEY=r'Software\Nemo\Nemoterm'
evidence=dict(completed=False,checks=[],screenshots=[],ui=[],
    executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    product_commit=os.environ.get('NEMOTERM_DPI_PRODUCT_COMMIT'))

def current():
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,ROOT_KEY) as key:
        try:return winreg.QueryValueEx(key,'UILanguage')
        except FileNotFoundError:return None

def set_preference(value):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,ROOT_KEY) as key:
        if value is None:
            try:winreg.DeleteValue(key,'UILanguage')
            except FileNotFoundError:pass
        else:winreg.SetValueEx(key,'UILanguage',0,winreg.REG_SZ,value)

def dialog_window(pid):
    found=[]
    @ENUM
    def visit(hwnd,_):
        owner=w.DWORD();name=c.create_unicode_buffer(64)
        u.GetWindowThreadProcessId(hwnd,c.byref(owner));u.GetClassNameW(hwnd,name,len(name))
        if owner.value==pid and name.value=='PuTTYConfigBox':found.append(hwnd)
        return True
    u.EnumWindows(visit,0)
    return next(iter(found),None)

@contextmanager
def terminal(profile_args,language=None):
    with OwnedJob() as job:
        language_args=['--ui-language',language] if language else []
        process=job.spawn([str(exe),*profile_args,*language_args,'--cols','40','--rows','12',
                           '-e','cmd.exe','/d','/q'],
                          env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
        hwnd=wait_for(lambda:find_window(process.pid))
        yield process,hwnd

def settings(process,terminal_hwnd,lang):
    u.PostMessageW(terminal_hwnd,0x111,0x50,0)
    hwnd=wait_for(lambda:dialog_window(process.pid))
    title=c.create_unicode_buffer(256);u.GetWindowTextW(hwnd,title,len(title))
    # Independent literal checks catch an English fallback or code-page corruption.
    assert ('配置' in title.value) if lang=='zh-CN' else ('Profile:' in title.value),title.value
    evidence['ui'].append(dict(language=lang,title=title.value))
    return hwnd

def probe(process,hwnd,lang,page='language',choice=None,action='stage'):
    command=[str(helper),str(process.pid),str(hwnd),str(u.GetDpiForWindow(hwnd)),page,lang]
    if choice is not None:command += [str(choice),action]
    result=subprocess.run(command,capture_output=True,text=True,timeout=25)
    value=json.loads(result.stdout)
    assert result.returncode==0 and value['completed'],(value,result.stderr)
    evidence['ui'].append(value)
    if choice is None or action=='stage':
        filename=f'i18n-{len(evidence["screenshots"]):02d}-{lang}-{page}.png'
        capture(hwnd,filename);evidence['screenshots'].append(filename)
    return value

def closed(hwnd):wait_for(lambda:not u.IsWindow(hwnd))

original=current()
try:
    # The hosted image uses an English display language; record Windows' actual
    # ordered UI preferences rather than inferring them from keyboard/locale.
    count=w.ULONG();size=w.ULONG()
    assert k.GetUserPreferredUILanguages(8,c.byref(count),None,c.byref(size))
    names=c.create_unicode_buffer(size.value)
    assert k.GetUserPreferredUILanguages(8,c.byref(count),names,c.byref(size))
    evidence['windows_ui_languages']=names[:size.value].split('\0')[:-2]
    assert any(tag.lower().startswith('en') for tag in evidence['windows_ui_languages'])
    with saved_profile(dict(NemoTabs=1,NemoRenderer=0,WarnOnClose=0)) as first, \
            saved_profile(dict(NemoTabs=0,NemoRenderer=0,WarnOnClose=0)) as second:
        set_preference('invalid-language')
        with terminal(first) as (process,term):
            hwnd=settings(process,term,'en')
            assert probe(process,hwnd,'en')['language_before']==0
            probe(process,hwnd,'en',choice=2,action='cancel');closed(hwnd)
            assert current()==('invalid-language',winreg.REG_SZ)
        evidence['checks'].append('invalid preference falls back to system; Cancel does not write')
        set_preference('en')
        with terminal(first,'zh-CN') as (process,term):
            hwnd=settings(process,term,'zh-CN')
            assert probe(process,hwnd,'zh-CN')['language_before']==1
            assert current()==('en',winreg.REG_SZ)
            probe(process,hwnd,'zh-CN',choice=0,action='cancel');closed(hwnd)
            assert current()==('en',winreg.REG_SZ)
        evidence['checks'].append('Chinese CLI override uses Unicode and does not persist; Cancel preserves English')
        with terminal(first) as (process,term):
            hwnd=settings(process,term,'en')
            probe(process,hwnd,'en',choice=2)
            probe(process,hwnd,'en',page='profile')
            assert probe(process,hwnd,'en')['language_before']==2
            assert current()==('en',winreg.REG_SZ)
            probe(process,hwnd,'en',choice=2,action='save');closed(hwnd)
            assert current()==('zh-CN',winreg.REG_SZ)
            hwnd=settings(process,term,'en')
            probe(process,hwnd,'en',choice=2,action='cancel');closed(hwnd)
        evidence['checks'].append('pending choice survives page changes; Save persists; existing process stays English')
        with terminal(second) as (process,term):
            hwnd=settings(process,term,'zh-CN')
            assert probe(process,hwnd,'zh-CN')['language_before']==2
            probe(process,hwnd,'zh-CN',choice=1,action='save');closed(hwnd)
            assert current()==('en',winreg.REG_SZ)
        evidence['checks'].append('restarted process with another profile uses saved Chinese; can switch back to English')
        with terminal(first) as (process,term):
            hwnd=settings(process,term,'en')
            probe(process,hwnd,'en',choice=0,action='save');closed(hwnd)
            assert current()==('system',winreg.REG_SZ)
        with terminal(second) as (process,term):
            hwnd=settings(process,term,'en')
            assert probe(process,hwnd,'en')['language_before']==0
            probe(process,hwnd,'en',choice=0,action='cancel');closed(hwnd)
        evidence['checks'].append('Follow Windows persists and resolves the actual English runner display language')
        for arguments in (first,second):
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,ROOT_KEY+'\\Sessions\\'+arguments[1]) as key:
                try:winreg.QueryValueEx(key,'UILanguage')
                except FileNotFoundError:pass
                else:raise AssertionError('Language preference leaked into a profile')
        evidence['checks'].append('UILanguage is global and absent from both profiles')
    evidence['completed']=True
finally:
    if original is None:set_preference(None)
    else:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,ROOT_KEY) as key:
            winreg.SetValueEx(key,'UILanguage',0,original[1],original[0])
    evidence['preference_restored']=current()==original
    (root/'research/i18n-interaction.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
print(json.dumps(evidence,indent=2))
