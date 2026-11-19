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
from memory_limits import private_ws_passes

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
    compare=os.environ.get('NEMOTERM_PAIR_READ_CELLS')=='1'
    view=ConsoleView(folder,compare_cells=compare)
    if compare:
        print('CELL中Z',flush=True)
        view.capture(); calibration=read_snapshot(folder/'peer-screen.json')
        write_snapshot(folder/'cell-calibration.json',calibration)
        assert 'CELL中Z' in calibration.get('text',''),calibration
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


def conversation():
    plan = [(PROMPT, REPLY)]
    for turn in range(1, 25):
        # The last line is unique to the reply. Use code blocks so the
        # real client lays out separate rows, including wide characters.
        lines = [f'row {turn:02d}.{n:02d}  中文  café  history' for n in range(1, 17)]
        reply = '```text\n' + '\n'.join(lines) + f'\n```\n\nACKTURN{turn:02d}DONE'
        plan.append((str(57000000 + turn), reply))
    return plan


def exercise_turns(out, desk, provider, stage, samples, rec, renderer_probe):
    rec['turns'] = []
    for turn, (prompt, reply) in enumerate(provider.turn_plan[1:], 1):
        label = stage[0] = f'turn-{turn:02d}'
        entry = dict(prompt=prompt, stage=label)
        rec['turns'].append(entry)
        def visible(needle):
            text = read_snapshot(out/'peer-screen.json').get('text', '')
            return text if needle in text else None
        for digit in prompt:
            desk.chord(ord(digit))
        wait_for(lambda: visible(prompt)); desk.chord(13)
        def received():
            assert not provider.errors, provider.errors
            return provider.chat_receipts[turn] if len(provider.chat_receipts) > turn else None
        receipt = wait_for(received, timeout=35)
        assert receipt['turn_prompts'] == [prompt] and receipt['reply_sha256'] == hashlib.sha256(reply.encode()).hexdigest()
        ack = f'ACKTURN{turn:02d}DONE'
        lines = reply.split('```')[1].splitlines()[1:]
        assert len(lines) == 16 and all(line.startswith(f'row {turn:02d}.') for line in lines)
        first_partial = False
        observed = {}
        def presented():
            nonlocal first_partial, observed
            assert not provider.errors, provider.errors
            if receipt.get('sent_sha256') != receipt['reply_sha256']:
                return None
            observed = read_snapshot(out/'peer-screen.json')
            frame = observed.get('text', '')
            if ack not in frame:
                return None
            assert observed['reader'] == 'ReadConsoleOutputW'
            # The client can paint the ack before it has redrawn the code block.
            # Require every expected line, in order before the ack, in one read.
            positions = [frame.find(line) for line in [*lines, ack]]
            if all(pos >= 0 for pos in positions) and positions == sorted(positions):
                return observed
            if not first_partial:
                write_snapshot(out/(label+'-first-ack-only.json'), observed)
                first_partial = True
            return None
        try:
            observed = wait_for(presented, timeout=30)
        except Exception:
            write_snapshot(out/(label+'-last-frame.json'), observed)
            raise
        frame = observed['text']
        write_snapshot(out/(label+'.json'), dict(prompt=prompt, reply_sha256=receipt['reply_sha256'], visible=frame,
                      reader=observed['reader'],legacy_available=observed['legacy_available'],legacy_ack_lines=observed['legacy_ack_lines']))
        time.sleep(5)  # include the quiet interval between normal user turns
        entry['memory'] = phase(samples, label)
        if renderer_probe is not None:
            entry['actual_renderer'] = renderer_probe()
            entry['within_budget'] = private_ws_passes(entry['actual_renderer'], entry['memory']['max']['private_ws'])
    assert len(provider.chat_receipts) == len(provider.turn_plan) and not provider.errors


def trial(out,kind,exe,client,font,rec,multi_turn=False):
    out.mkdir();home,work,env=isolated_home(out);env.update(HOME=str(home),GIT_ALLOW_PROTOCOL='file',GIT_TERMINAL_PROMPT='0',NEMOTERM_HOSTED_REFERENCE='1')
    if kind=='pterm':env.pop('NEMOTERM_CONPTY',None)
    provider=Provider();provider.selection=False;thread=threading.Thread(target=provider.serve_forever,daemon=True);thread.start()
    if multi_turn:
        env['NEMOTERM_PAIR_READ_CELLS']='1'
        provider.turn_lock = threading.Lock()
        provider.chat_receipts = []
        provider.auxiliary_count = 0
        provider.turn_plan = conversation()
        provider.turn_prompts = {prompt for prompt, _ in provider.turn_plan}
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
                stage[0]='agent_reply';time.sleep(3)
                if multi_turn:
                    exercise_turns(out,desk,provider,stage,rec['samples'],rec,None if kind=='pterm' else actual)
                stop.set();sampler.join(3)
                assert not sampler.is_alive() and not errors, errors
                rec['empty']=phase(rec['samples'],'empty');rec['agent_reply']=phase(rec['samples'],'agent_reply')
                if multi_turn:
                    rec['whole_run_peak']={field:max(s[field] for s in rec['samples']) for field in FIELDS}
                if kind!='pterm':
                    rec['renderer_after']=actual();assert rec['renderer_after']==target+1
                final_phase='after_conversation' if multi_turn else 'agent_reply'
                rec['resident_backing'][final_phase]=resident_backing(handle,exe)
                runtime_snapshot(rec,final_phase,handle,job,exe,client)
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
            if multi_turn:
                rec['chat_requests'] = len(provider.chat_receipts)
                rec['auxiliary_requests'] = provider.auxiliary_count
                assert rec['chat_requests'] == len(provider.turn_plan)
                assert rec['chat_requests']+rec['auxiliary_requests'] == len(provider.requests)
            if multi_turn and kind!='pterm':
                assert all(e['actual_renderer']==target+1 and e['within_budget'] for e in rec['turns']),rec['turns']
                assert private_ws_passes(target+1,rec['whole_run_peak']['private_ws']),rec['whole_run_peak']
    finally:
        provider.shutdown();provider.server_close();thread.join(3)
        try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,reg)
        except FileNotFoundError:pass


def main():
    # A failed frame can contain glyphs absent from the hosted log code page.
    # Keep the Unicode traceback in summary.json and continue with the next renderer.
    if sys.stdout is not None:sys.stdout.reconfigure(errors='backslashreplace')
    if sys.argv[1:2]==['--peer']:return peer(Path(sys.argv[2]),sys.argv[3:])
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise RuntimeError('GitHub-hosted Windows required')
    parser=argparse.ArgumentParser();parser.add_argument('--pterm',type=Path,required=True);parser.add_argument('--codex',type=Path,required=True);parser.add_argument('--multi-turn',action='store_true');p=parser.parse_args()
    original=p.pterm.resolve(strict=True);client=p.codex.resolve(strict=True);candidate=Path(os.environ['NEMOTERM_TEST_EXE']).resolve(strict=True)
    assert digest(original)==PTERM and digest(client)==CODEX
    out=ROOT/'build/paired-agent-memory';out.mkdir(parents=True,exist_ok=False)
    kinds=('pterm','nemoterm-tab','nemoterm-standalone','nemoterm-directx-tab','nemoterm-directx-standalone');report=dict(fixture_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),cases={})
    order=('pterm','nemoterm-tab','nemoterm-directx-tab') if p.multi_turn else (*kinds,*reversed(kinds))
    report['scenario']='24-followups' if p.multi_turn else 'paired-short-session'
    for i,kind in enumerate(order,1):
        name=f'{i}-{kind}';entry=report['cases'][name]=dict(passed=False)
        try:trial(out/name,kind,original if kind=='pterm' else candidate,client,os.environ['NEMOTERM_TEST_FONT'],entry,p.multi_turn);entry['passed']=True
        except Exception:entry['error']=traceback.format_exc();print(name,entry['error'],flush=True)
        finally:write_snapshot(out/'summary.json',report)
    return int(not all(r['passed'] for r in report['cases'].values()))

if __name__=='__main__':sys.exit(main())
