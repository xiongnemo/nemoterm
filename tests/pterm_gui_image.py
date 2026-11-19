"""Real keyboard image-paste observations on two independently identified frontends."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback
import uuid
import winreg

from agent_clipboard_fixture import Provider, codex_command, isolated_home, put_bitmap
from clipboard_test_utils import SavedClipboard
from fixture_io import read_snapshot, write_snapshot
from hosted_gesture_input import DesktopInput
from native_test_utils import c, w, capture, terminal_host, u, wait_for
from owned_job import OwnedJob
from paired_agent_memory import ROOT, PTERM, CODEX, digest, gui


def observe(folder, kind, exe, client, phase, binding, rec):
    folder.mkdir()
    home, work, env = isolated_home(folder)
    env.update(HOME=str(home), GIT_ALLOW_PROTOCOL='file', GIT_TERMINAL_PROMPT='0', NEMOTERM_HOSTED_REFERENCE='1')
    if kind=='pterm':env.pop('NEMOTERM_CONPTY',None)
    # The in-console observer records the currently rendered client cells identically on both hosts.
    env['NEMOTERM_PAIR_READ_CELLS']='1'
    server=Provider();server.selection=False;server.capture_gui_draft=True
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    profile='image-'+uuid.uuid4().hex
    key_path=('Software\\SimonTatham\\PuTTY' if kind=='pterm' else 'Software\\Nemo\\Nemoterm')+'\\Sessions\\'+profile
    font=os.environ['NEMOTERM_TEST_FONT']
    rec.update(host=kind,phase=phase,binding=binding,font=font,terminal_sha256=digest(exe),client_sha256=digest(client))
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,key_path) as key:
            opts=dict(Font=font,FontHeight=10,TermWidth=160,TermHeight=48,LineCodePage='UTF-8',WarnOnClose=0,CloseOnExit=1)
            if kind!='pterm':opts['NemoRenderer']=0
            for k,v in opts.items():winreg.SetValueEx(key,k,0,winreg.REG_SZ if isinstance(v,str) else winreg.REG_DWORD,v)
        codex=codex_command(str(client),home,work,env,f'http://127.0.0.1:{server.server_port}/v1')
        args=[str(exe),'-load',profile]+([] if kind=='pterm' else ['--no-tabs'])+['-e',sys.executable,str(ROOT/'tests/paired_agent_memory.py'),'--peer',str(folder),*codex]
        with OwnedJob() as job:
            proc=job.spawn(args,cwd=work,env=env,creationflags=subprocess.CREATE_NO_WINDOW);clip=desk=None
            try:
                rec['grid']=wait_for(lambda:read_snapshot(folder/'grid.json'),timeout=30)['grid'];assert rec['grid']==[160,48]
                hwnd=wait_for(lambda:gui(proc.pid,kind));host=terminal_host(hwnd);assert host==hwnd
                cls=c.create_unicode_buffer(128);u.GetClassNameW(hwnd,cls,len(cls));rec['window_class']=cls.value
                if kind!='pterm':
                    u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
                    rec['renderer']=int(u.GetPropW(hwnd,'NemotermRenderer') or 0);assert rec['renderer']==1
                desk=DesktopInput(proc.pid,host,hwnd,rec.setdefault('desktop',{}));clip=SavedClipboard(hwnd);put_bitmap(hwnd)
                write_snapshot(folder/'launch.json',{'start':True})
                def text():return read_snapshot(folder/'peer-screen.json').get('text','')
                def visible(marker):
                    def check():
                        s=text();return s if marker in s else None
                    return check
                def inputs(digits):
                    for digit in digits:desk.chord(ord(digit))
                def marked(r,marker):
                    return any(v.strip().removesuffix('[Image #1]').rstrip()==marker for v in r.get('gui_drafts',[]))
                def receipt(marker):
                    return next((r for r in server.requests if marked(r,marker)),None)
                wait_for(visible('Ask Codex'),timeout=80)
                if phase=='after-turn':
                    inputs('3721');wait_for(visible('3721'));desk.chord(13)
                    wait_for(lambda:receipt('3721'),timeout=30);wait_for(visible('NEMOTERM_TEXT_ACCEPTED'),timeout=30)
                inputs('8932');rec['marker_screen']=wait_for(visible('8932'));rec['marker_ns']=time.perf_counter_ns()
                rec['key_ns']=time.perf_counter_ns();desk.chord(*([17,86] if binding=='ctrl-v' else [17,16,86]))
                try:
                    rec['attachment_screen']=wait_for(visible('[Image'),timeout=10);rec['visible']=True
                except AssertionError:
                    rec['attachment_screen']=text();rec['visible']=False
                capture(hwnd,str(folder/'before-submit.png'))
                desk.chord(13);wait_for(lambda:receipt('8932'),timeout=30)
                target=[r for r in server.requests if marked(r,'8932')];assert len(target)==1
                imgs=target[0]['images'];rec['images']=imgs
                assert len(imgs)<=1 and all(im['generated_pixels_match'] for im in imgs) and target[0]['path']=='/v1/responses'
                rec['reply']=wait_for(visible('NEMOTERM_IMAGE_ACCEPTED' if imgs else 'NEMOTERM_TEXT_ACCEPTED'),timeout=30)
                assert not server.errors
                rec['clipboard_owned_at_restore']=u.GetClipboardOwner()==hwnd;clip.restore();clip=None
                desk.chord(17,67);time.sleep(.35)
                if proc.poll() is None and u.IsWindow(hwnd):desk.chord(17,67)
                rec['exit']=proc.wait(timeout=20);assert rec['exit']==0
            finally:
                try:
                    if clip:clip.restore()
                finally:
                    if desk:desk.restore()
                    rec['cleanup']=job.finish();rec['requests']=server.requests;rec['provider_errors']=server.errors
                    rec['final_screen']=read_snapshot(folder/'peer-screen.json').get('text','')
            assert not rec['cleanup']['terminated_remaining'] and rec['clipboard_owned_at_restore']
            rec['observed']=True
    finally:
        server.shutdown();server.server_close();thread.join(3)
        try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,key_path)
        except FileNotFoundError:pass


if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    p=argparse.ArgumentParser();p.add_argument('--pterm',required=True,type=Path);p.add_argument('--codex',required=True,type=Path);args=p.parse_args()
    ref=args.pterm.resolve(strict=True);client=args.codex.resolve(strict=True);candidate=Path(os.environ['NEMOTERM_TEST_EXE']).resolve(strict=True)
    assert digest(ref)==PTERM and digest(client)==CODEX
    out=ROOT/'build/paired-gui-images';out.mkdir();report=dict(cases={})
    for phase in ('first-marker','after-turn'):
        for binding in ('ctrl-v','ctrl-shift-v'):
            for host,image in (('pterm',ref),('nemoterm',candidate)):
                name=f'{host}-{phase}-{binding}';r=report['cases'][name]={}
                try:observe(out/name,host,image,client,phase,binding,r)
                except Exception:r['error']=traceback.format_exc()
                finally:write_snapshot(out/'summary.json',report)
    # Stable Ctrl+V on each real GUI is a positive control before interpreting early input.
    # A different stock binding policy is an observation, never a product pass.
    assert all(r.get('observed') for r in report['cases'].values())
    assert all(report['cases'][f'{host}-after-turn-ctrl-v']['images'] for host in ('pterm','nemoterm'))
