"""Compare one physical bitmap-paste gesture per draft on the actual Win32 frontends."""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from PIL import ImageGrab
from agent_clipboard_fixture import Provider,codex_command,isolated_home,put_bitmap
from clipboard_test_utils import SavedClipboard
from fixture_io import read_snapshot,write_snapshot
from hosted_gesture_input import DesktopInput,ThreadInfo
from native_test_utils import c,w,u,wait_for,capture
from owned_job import OwnedJob
from owned_window_focus import focus_owned_window
from paired_agent_memory import ROOT,CODEX,digest,peer
from pterm_gui_image import observe,paste_and_submit

PROFILE='{86ed62c6-7b38-45ba-9235-58ebce1ad56d}'
u.IsChild.argtypes=[w.HWND,w.HWND]
u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
u.GetGUIThreadInfo.argtypes=[w.DWORD,c.POINTER(ThreadInfo)]
u.GetSystemMetrics.argtypes=[c.c_int]


def gui(pid):
    windows=[]
    @c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
    def visit(h,_):
        owner=w.DWORD();name=c.create_unicode_buffer(128)
        if u.GetWindowThreadProcessId(h,c.byref(owner)) and owner.value==pid and u.IsWindowVisible(h):
            u.GetClassNameW(h,name,len(name))
            if name.value=='CASCADIA_HOSTING_WINDOW_CLASS':windows.append(h)
        return True
    u.EnumWindows(visit,0)
    assert len(windows)<=1,windows
    return windows[0] if windows else None


def focused(host,pid):
    if u.GetForegroundWindow()!=host:return None
    info=ThreadInfo(size=c.sizeof(ThreadInfo));owner=w.DWORD()
    if not u.GetGUIThreadInfo(0,c.byref(info)) or not info.focus:return None
    if info.focus!=host and not u.IsChild(host,info.focus):return None
    return info.focus if u.GetWindowThreadProcessId(info.focus,c.byref(owner)) and owner.value==pid else None


def settings(exe,folder,policy):
    raw=(ROOT/'build/wt-reference/userDefaults.json').read_text(encoding='utf-8-sig')
    data=json.loads(re.sub(r'(?m)^\s*//[^\n]*','',raw)); keys=data['keybindings']
    stock=next(k for k in keys if k['keys']=='ctrl+v'); assert stock['id']=='Terminal.PasteFromClipboard'
    if policy=='forward-ctrl-v':stock['id']=None
    data.update(defaultProfile=PROFILE,initialRows=48,initialCols=160,windowingBehavior='useNew',confirmCloseAllTabs=False)
    data['profiles']['list'].append(dict(guid=PROFILE,name='Bitmap reference',font=dict(face=os.environ['NEMOTERM_TEST_FONT'],size=10),closeOnExit='always',commandline='cmd.exe'))
    write_snapshot(exe.parent/'settings/settings.json',data);write_snapshot(folder/'reference-settings.json',data)


def session(out,exe,client,phase,binding,policy,rec):
    out.mkdir();settings(exe,out,policy);home,work,env=isolated_home(out);env.pop('NEMOTERM_CONPTY',None)
    env.update(HOME=str(home),GIT_ALLOW_PROTOCOL='file',GIT_TERMINAL_PROMPT='0',NEMOTERM_PAIR_READ_CELLS='1',NEMOTERM_HOSTED_REFERENCE='1')
    server=Provider();server.selection=False;server.capture_gui_draft=True
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    rec.update(host='windows-terminal',binding=binding,phase=phase,policy=policy,terminal_sha256=digest(exe),client_sha256=digest(client),font=os.environ['NEMOTERM_TEST_FONT'])
    try:
        cmd=codex_command(str(client),home,work,env,f'http://127.0.0.1:{server.server_port}/v1')
        # The actual client only inherits the isolated allowlisted environment, even if WT reconstructs the shell environment.
        write_snapshot(out/'peer-config.json',dict(env=env,command=cmd))
        # The reference GUI needs the runner's actual Windows profile paths for WinUI and settings.
        # Only the GUI/wrapper use them: the peer replaces its environment before starting Codex.
        frontend_env={name:value for name,value in os.environ.items() if name.upper() in {
            'SYSTEMROOT','WINDIR','COMSPEC','PATH','PATHEXT','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMW6432',
            'COMMONPROGRAMFILES','COMMONPROGRAMFILES(X86)','PROGRAMDATA','ALLUSERSPROFILE','PROCESSOR_ARCHITECTURE',
            'NUMBER_OF_PROCESSORS','SYSTEMDRIVE','USERNAME','USERDOMAIN','USERPROFILE','APPDATA','LOCALAPPDATA',
            'TEMP','TMP','HOMEDRIVE','HOMEPATH','PUBLIC','COMPUTERNAME'}}
        args=[str(exe),'-w','new','--size','160,48','new-tab','-p','Bitmap reference','-d',str(work),sys.executable,str(Path(__file__).resolve()),'--peer',str(out)]
        with OwnedJob() as job:
            proc=job.spawn(args,cwd=work,env=frontend_env,creationflags=subprocess.CREATE_NO_WINDOW);desk=clip=None;host=None
            try:
                rec['stage']='launch';rec['launcher_pid']=proc.pid
                def launched():
                    failure=read_snapshot(out/'peer-error.json')
                    if failure:raise RuntimeError(failure['traceback'])
                    record=read_snapshot(out/'grid.json')
                    if record:return record
                    if proc.poll() is not None:raise RuntimeError(f'Windows Terminal exited {proc.returncode} before the console peer opened')
                rec['grid']=wait_for(launched,timeout=40); assert rec['grid']['grid']==[160,48],rec['grid']
                rec['wt_environment']=read_snapshot(out/'peer-terminal.json');assert rec['wt_environment']['WT_PROFILE_ID'].lower()==PROFILE and rec['wt_environment']['WT_SESSION'],rec['wt_environment']
                host=wait_for(lambda:gui(proc.pid));rec['host_hwnd']=host
                rec['stage']='foreground';focus_owned_window(host,proc.pid,mode='synchronized',record=rec.setdefault('initial_focus',{}))
                key_hwnd=wait_for(lambda:focused(host,proc.pid));rec['keyboard_hwnd']=key_hwnd
                desk=DesktopInput(proc.pid,host,key_hwnd,rec.setdefault('desktop',{}));clip=SavedClipboard(host);put_bitmap(host)
                def shot():
                    desk.target();r=w.RECT();assert u.GetClientRect(host,c.byref(r));origin=w.POINT();assert u.ClientToScreen(host,c.byref(origin))
                    x,y=origin.x,origin.y;w0,h0=r.right,r.bottom
                    assert 0<=x<x+w0<=u.GetSystemMetrics(0) and 0<=y<y+h0<=u.GetSystemMetrics(1),(x,y,w0,h0)
                    im=ImageGrab.grab(bbox=(x,y,x+w0,y+h0));desk.target();im.save(out/'before-submit.png')
                    rec['capture']=dict(method='foreground owned client rectangle',size=list(im.size))
                rec['stage']='paste';paste_and_submit(out,phase,binding,desk,server,rec,shot)
                assert rec['visible']==bool(rec['images']);rec['stage']='close'
                rec['clipboard_owned_at_restore']=u.GetClipboardOwner()==host;clip.restore();clip=None;assert rec['clipboard_owned_at_restore']
                desk.chord(17,67);time.sleep(.35)
                if proc.poll() is None and u.IsWindow(host):desk.chord(17,67)
                rec['exit']=proc.wait(timeout=20);assert rec['exit']==0
            except Exception:
                try:
                    win=gui(proc.pid)
                    if win:capture(win,str(out/'failure-window.png'))
                except Exception:rec['failure_capture_error']=traceback.format_exc()
                raise
            finally:
                rec['root_exit_before_cleanup']=proc.poll()
                try:
                    if clip:clip.restore()
                finally:
                    if desk:desk.restore()
                    rec['cleanup']=job.finish();rec['requests']=server.requests;rec['provider_errors']=server.errors
                    rec['final_screen']=read_snapshot(out/'peer-screen.json').get('text','')
            assert not rec['cleanup']['terminated_remaining'];rec['observed']=True
    finally:server.shutdown();server.server_close();thread.join(3)


def main():
    if len(sys.argv)==3 and sys.argv[1]=='--peer':
        out=Path(sys.argv[2]);config=read_snapshot(out/'peer-config.json');assert Path(config['env']['CODEX_HOME'])==out/'home'
        assert os.environ.get('WT_SESSION');write_snapshot(out/'peer-terminal.json',{k:os.environ.get(k,'') for k in ('WT_SESSION','WT_PROFILE_ID')})
        try:
            os.environ.clear();os.environ.update(config['env']);return peer(out,config['command'])
        except Exception:
            write_snapshot(out/'peer-error.json',{'traceback':traceback.format_exc()});raise
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    p=argparse.ArgumentParser();p.add_argument('--codex',type=Path,required=True);args=p.parse_args();client=args.codex.resolve(strict=True);assert digest(client)==CODEX
    exe=Path(os.environ['NEMOTERM_WT_REFERENCE']);product=Path(os.environ['NEMOTERM_TEST_EXE']);out=ROOT/'build/wt-images';out.mkdir()
    report=dict(cases={},reference=read_snapshot(ROOT/'build/wt-reference/identity.json'));assert digest(exe)==report['reference']['frontend_sha256']
    for phase in ('first-marker','after-turn'):
        for binding in ('ctrl-v','ctrl-shift-v'):
            for host in ('windows-stock','nemoterm','forward-ctrl-v'):
                if host=='forward-ctrl-v' and binding!='ctrl-v':continue
                name=f'{host}-{phase}-{binding}';r=report['cases'][name]={}
                try:
                    if host=='nemoterm':observe(out/name,host,product,client,phase,binding,r)
                    else:session(out/name,exe,client,phase,binding,host,r)
                except Exception:r['error']=traceback.format_exc(); print(name,r['error'],flush=True)
                finally:write_snapshot(out/'summary.json',report)
    assert all(r.get('observed') for r in report['cases'].values())
    for name in ('forward-ctrl-v-after-turn-ctrl-v','nemoterm-after-turn-ctrl-v','nemoterm-after-turn-ctrl-shift-v'):
        assert len(report['cases'][name]['images'])==1,name
    return 0

if __name__=='__main__':sys.exit(main())
