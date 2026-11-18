"""Compare the exact pterm 0.85 with the exact Nemoterm image on a single hosted desktop."""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time
import traceback
import uuid
import winreg

from agent_clipboard_fixture import Provider, codex_command, isolated_home
from console_frame_observer import ConsoleView
from fixture_io import read_snapshot, write_snapshot
from frontend_runtime_snapshot import snapshot as runtime_snapshot
from native_test_utils import capture, find_window, k, memory_sample, terminal_host, u, wait_for
from owned_job import OwnedJob
from paired_residency import resident_backing

ROOT=Path(__file__).resolve().parents[1]
PTERM='8580a3df4afe7696758c1cef43d0e88e3db5fd41c35c60166241aee72dd3ba3b'
CODEX='edfdd48f8b458af0906e507b4cb05217b326c3d6e515e9f024e05e3b8d650f70'
FIELDS=('private_ws','total_ws','private_commit')
PROMPT='NEMOTERM_MEMORY_PAIR'
REPLY='NEMOTERM_TEXT_ACCEPTED'


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def peer(folder, command):
    # This controller is a separate console child in all arms, never counted
    # as part of a frontend. It never reads user input or modifies its content.
    view=ConsoleView(folder)
    sys.stdout.write('NEMOTERM_MEMORY_BASELINE\r\n');sys.stdout.flush()
    write_snapshot(folder/'grid.json',dict(grid=list(os.get_terminal_size(1)),pid=os.getpid()))
    wait_for(lambda:read_snapshot(folder/'launch.json').get('start'),timeout=25)
    child=subprocess.Popen(command)
    while child.poll() is None:
        view.capture();time.sleep(.05)
    return child.returncode


def gui(pid,kind):
    if kind!='pterm':return find_window(pid)
    matches=[]
    @c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
    def visit(hwnd,_):
        owner=w.DWORD();u.GetWindowThreadProcessId(hwnd,c.byref(owner));rect=w.RECT()
        if owner.value==pid and u.IsWindowVisible(hwnd) and u.GetClientRect(hwnd,c.byref(rect)) and rect.right>=700 and rect.bottom>=450:
            matches.append(hwnd)
        return True
    u.EnumWindows(visit,0)
    return matches[0] if len(matches)==1 else None


def phase(samples,label):
    selected=[s for s in samples if s['phase']==label]
    assert len(selected)>=10 and selected[-1]['t']-selected[0]['t']>=1, (label,len(selected))
    return dict(samples=len(selected),seconds=selected[-1]['t']-selected[0]['t'],
        median={k:statistics.median(s[k] for s in selected) for k in FIELDS},max={k:max(s[k] for s in selected) for k in FIELDS})


def trial(out,kind,exe,client,font,rec):
    out.mkdir();home,work,env=isolated_home(out);env.update(HOME=str(home),GIT_ALLOW_PROTOCOL='file',GIT_TERMINAL_PROMPT='0',NEMOTERM_HOSTED_REFERENCE='1')
    if kind=='pterm':env.pop('NEMOTERM_CONPTY',None)
    provider=Provider();provider.selection=False;thread=threading.Thread(target=provider.serve_forever,daemon=True);thread.start()
    name='pair-'+uuid.uuid4().hex
    reg=('Software\\SimonTatham\\PuTTY\\Sessions\\' if kind=='pterm' else 'Software\\Nemo\\Nemoterm\\Sessions\\')+name
    options=dict(Font=font,FontIsBold=0,FontHeight=10,FontCharSet=0,TermWidth=160,TermHeight=48,LineCodePage='UTF-8',CloseOnExit=1,WarnOnClose=0)
    is_tab=kind in ('nemoterm-tab','nemoterm-directx-tab')
    target=2 if kind.startswith('nemoterm-directx-') else 0
    if kind!='pterm':options.update(NemoRenderer=target)
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,reg) as key:
            for keyname,value in options.items():winreg.SetValueEx(key,keyname,0,winreg.REG_DWORD if isinstance(value,int) else winreg.REG_SZ,value)
        rec.update(profile=options,terminal_sha256=digest(exe),client_sha256=digest(client),kind=kind,samples=[])
        cmd=codex_command(str(client),home,work,env,f'http://127.0.0.1:{provider.server_port}/v1')+[PROMPT]
        frontend=[str(exe),'-load',name]+([] if kind=='pterm' else ['--tabs' if is_tab else '--no-tabs'])
        with OwnedJob() as job:
            proc=job.spawn(frontend+['-e',sys.executable,str(Path(__file__).resolve()),'--peer',str(out),*cmd],cwd=work,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
            # The query handle belongs to this exact job-owned PID. Never
            # trim, suspend, minimize or attach instrumentation to either app.
            handle=k.OpenProcess(0x0410,False,proc.pid);assert handle
            desk=None;sampler=None;stop=threading.Event();errors=[];stage=['launch'];start=time.monotonic()
            def sample():
                try:
                    while not stop.is_set():
                        rec['samples'].append(dict(t=time.monotonic()-start,phase=stage[0],**memory_sample(handle)));stop.wait(.1)
                except Exception:errors.append(traceback.format_exc())
            try:
                sampler=threading.Thread(target=sample,daemon=True);sampler.start()
                grid=wait_for(lambda:read_snapshot(out/'grid.json'),timeout=30);rec['console']=grid;assert grid['grid']==[160,48],grid
                hwnd=wait_for(lambda:gui(proc.pid,kind),timeout=15);host=terminal_host(hwnd);assert bool(host!=hwnd)==is_tab
                from hosted_gesture_input import DesktopInput
                desk=DesktopInput(proc.pid,host,hwnd,rec.setdefault('desktop',{}));cls=c.create_unicode_buffer(120);u.GetClassNameW(hwnd,cls,len(cls));r=w.RECT();assert u.GetClientRect(hwnd,c.byref(r))
                rec['view']=dict(class_name=cls.value,client_px=[r.right,r.bottom],is_tab=host!=hwnd)
                if kind!='pterm':
                    u.GetPropW.argtypes=[w.HWND,w.LPCWSTR];u.GetPropW.restype=w.HANDLE
                    actual=lambda:int(u.GetPropW(hwnd,'NemotermRenderer') or 0)
                    wait_for(lambda:actual()==target+1,timeout=5)
                    rec['renderer_before']=actual();assert rec['renderer_before']==target+1
                stage[0]='empty';time.sleep(2);stage[0]='empty_census'
                rec['resident_backing']={'empty':resident_backing(handle,exe)}
                stage[0]='starting_agent';write_snapshot(out/'launch.json',dict(start=True))
                wait_for(lambda:any(row['path']=='/v1/responses' and PROMPT in row['text'] for row in provider.requests),timeout=85)
                def replied():
                    text=read_snapshot(out/'peer-screen.json').get('text','')
                    return text if PROMPT in text and REPLY in text else None
                content=wait_for(replied,timeout=30);write_snapshot(out/'accepted.json',dict(text=content))
                stage[0]='agent_reply';time.sleep(3);stop.set();sampler.join(3)
                assert not sampler.is_alive() and not errors, errors
                rec['empty']=phase(rec['samples'],'empty');rec['agent_reply']=phase(rec['samples'],'agent_reply')
                if kind!='pterm':
                    rec['renderer_after']=actual();assert rec['renderer_after']==target+1
                rec['resident_backing']['agent_reply']=resident_backing(handle,exe)
                runtime_snapshot(rec,'agent_reply',handle,job,exe,client)
                # Only after the final measurement, preserve what the frontend
                # actually painted; capture is outside the memory interval.
                rgb=capture(hwnd,return_pixels=True);from PIL import Image
                image=Image.frombytes('RGB',(r.right,r.bottom),rgb);assert len(image.getcolors(image.width*image.height))>2
                image.save(out/'frontend.png');rec['pixels_sha256']=hashlib.sha256(rgb).hexdigest()
                desk.chord(0x11,0x43);time.sleep(.35)
                if proc.poll() is None and u.IsWindow(hwnd):desk.chord(0x11,0x43)
                rec['exit_code']=proc.wait(timeout=20);assert rec['exit_code']==0
            finally:
                stop.set()
                if sampler:sampler.join(3)
                if desk:desk.restore()
                k.CloseHandle(handle);rec['sample_errors']=errors;rec['requests']=provider.requests;rec['provider_errors']=provider.errors;rec['cleanup']=job.finish()
            assert not provider.errors and not rec['cleanup']['terminated_remaining'],rec['cleanup']
    finally:
        provider.shutdown();provider.server_close();thread.join(3)
        try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,reg)
        except FileNotFoundError:pass


def main():
    if sys.argv[1:2]==['--peer']:return peer(Path(sys.argv[2]),sys.argv[3:])
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise RuntimeError('GitHub-hosted Windows required')
    parser=argparse.ArgumentParser();parser.add_argument('--pterm',type=Path,required=True);parser.add_argument('--codex',type=Path,required=True);p=parser.parse_args()
    original=p.pterm.resolve(strict=True);client=p.codex.resolve(strict=True);candidate=Path(os.environ['NEMOTERM_TEST_EXE']).resolve(strict=True)
    assert digest(original)==PTERM and digest(client)==CODEX
    out=ROOT/'build/paired-agent-memory';out.mkdir(parents=True,exist_ok=False)
    kinds=('pterm','nemoterm-tab','nemoterm-standalone','nemoterm-directx-tab','nemoterm-directx-standalone');report=dict(fixture_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),cases={})
    for i,kind in enumerate((*kinds,*reversed(kinds)),1):
        name=f'{i}-{kind}';entry=report['cases'][name]=dict(passed=False)
        try:trial(out/name,kind,original if kind=='pterm' else candidate,client,os.environ['NEMOTERM_TEST_FONT'],entry);entry['passed']=True
        except Exception:entry['error']=traceback.format_exc();print(name,entry['error'],flush=True)
        finally:write_snapshot(out/'summary.json',report)
    return int(not all(r['passed'] for r in report['cases'].values()))

if __name__=='__main__':sys.exit(main())
