"""Shift-select a real client reply in an actual GDI or DirectX tab and submit the copied text."""
import argparse
from collections import Counter
import io
import os
import re
import hashlib
import json
import zipfile
import struct
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import unicodedata
from pathlib import Path
from PIL import Image

from agent_clipboard_fixture import SELECTION_PREFIX, SELECTION_TEXT, SELECTION_STABLE, SELECTION_TRIGGER
from clipboard_test_utils import clipboard_text
from fixture_io import read_snapshot, write_snapshot
from native_test_utils import u, k, wait_for, memory_sample
from memory_limits import private_ws_policy, private_ws_passes
from owned_job import OwnedJob
from frontend_runtime_snapshot import snapshot as runtime_snapshot

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import nemoterm_debug as api


def claude_reference(client_hash):
    # Both independent terminal hosts recorded exactly one complete user part
    # with this spelling from the same pinned client and decomposed input.
    path=ROOT/'tests/claude-independent-unicode.zip'
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest=='97555c76b216fe811964f87c354d1edfb31801130b860f88f8e9b4f1bd70344c',digest
    with zipfile.ZipFile(path) as archive:
        ref=json.loads(archive.read('unicode-boundary/summary.json'))
        assert ref['client_sha256']==client_hash,(ref['client_sha256'],client_hash)
        expected=b'\x1b[200~'+(SELECTION_PREFIX+SELECTION_TEXT).encode()+b'\x1b[201~'
        for host in ('system-claude','winpty-claude'):
            case=ref['cases'][host];request,=case['requests']
            assert case['passed'] and not case['cleanup']['terminated_remaining'] and case['form']=='NFC'
            assert bytes.fromhex(case['sent_hex'])==expected and expected in archive.read('unicode-boundary/'+host+'/reference-stdin.vt')
            assert request['selection_nfc_present'] and not request['selection_received'] and request['path']=='/v1/messages'
            assert request['text']==['NEMOTERM_SUBMIT','NEMOTERM_SELECT'] and request['advertised_tools']==0
    return dict(artifact_sha256=digest,client_sha256=client_hash,form='NFC')


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise SystemExit('Client interaction requires a GitHub-hosted runner')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client',choices=('codex','opencode','claude'),default='opencode')
    parser.add_argument('--client-exe',required=True)
    parser.add_argument('--font',required=True)
    parser.add_argument('--renderer',choices=('gdi','directx'),required=True)
    parser.add_argument('--stable-unicode',action='store_true')
    parser.add_argument('--default-grid',action='store_true',help='Require actual 160x48 and sample the untouched frontend throughout interaction')
    parser.add_argument('--system-input',action='store_true')
    parser.add_argument('--right-click',choices=('default','copy-paste'))
    args=parser.parse_args()
    sample_text=SELECTION_STABLE if args.stable_unicode else SELECTION_TEXT
    assert not args.right_click or args.system_input
    out=ROOT/'research';out.mkdir(exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix=args.client+'-selection-',dir=ROOT/'build'))
    case=folder/'client'; report=case/'observed.json'; control=case/'control.json'
    tag=args.client+'-selection-'+args.renderer+('-system' if args.system_input else '')
    if args.right_click:tag+='-right-'+args.right_click
    evidence=dict(completed=False,client=args.client,font=args.font,requested_renderer=args.renderer,checks=[],screenshots=[],global_input=args.system_input,frontend_samples=[])
    with OwnedJob() as job,(folder/'fixture.log').open('w',encoding='utf-8') as log:
        proc=job.spawn([sys.executable,str(ROOT/'tests/agent_clipboard_fixture.py'),
            '--client',args.client,'--client-exe',str(Path(args.client_exe).resolve()),
            '--terminal',os.environ['NEMOTERM_TEST_EXE'],'--directory',str(case),
            '--automation','--selection-renderer',args.renderer,'--font',args.font]+
            (['--default-grid'] if args.default_grid else [])+
            (['--stable-unicode'] if args.stable_unicode else [])+
            (['--right-copy-and-paste'] if args.right_click=='copy-paste' else []),stdout=log,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
        def child():
            value=read_snapshot(report);assert proc.poll() is None and not value.get('errors'),value
            return value
        endpoint=seat=handle=desktop=sampler=None
        stop=threading.Event();samples=[];sample_errors=[]
        try:
            observed=wait_for(child,timeout=40)
            instance=wait_for(lambda: next(iter(api.discover(observed['pid'])),None),timeout=20)
            endpoint=instance['endpoint'];session,=instance['sessions'];seat=session['id'];hwnd=session['hwnd']
            evidence['session']=session
            assert instance['pid']==observed['pid'] and hwnd==observed['hwnd'] and session['active'] and session['renderer']=={'gdi':0,'directx':2}[args.renderer],session
            assert hwnd!=session['window'],'Expected the default multi-tab host'
            handle=k.OpenProcess(0x0410,False,observed['pid']);assert handle
            actual=session['renderer']+1
            if args.default_grid:
                assert (session['cols'],session['rows'])==(160,48),session
                started=time.monotonic()
                def sample_running():
                    try:
                        while not stop.is_set():
                            samples.append(dict(seconds=time.monotonic()-started,**memory_sample(handle)))
                            stop.wait(.1)
                    except Exception:sample_errors.append(traceback.format_exc())
                sampler=threading.Thread(target=sample_running,daemon=True);sampler.start()
            def sample(phase):
                evidence['frontend_samples'].append(dict(phase=phase,**memory_sample(handle)))
                if phase in ('startup','submitted'):
                    runtime_snapshot(evidence,phase,handle,job,os.environ['NEMOTERM_TEST_EXE'],args.client_exe)
            text=lambda:api.request(endpoint,'text',seat)
            def key(vk,mods=0):api.request(endpoint,'key',seat,struct.pack('<II',vk,mods))
            if args.system_input:
                from hosted_gesture_input import DesktopInput
                evidence['desktop']={}
                desktop=DesktopInput(observed['pid'],session['window'],hwnd,evidence['desktop'])
            def press(vk,mods=0):
                if desktop:
                    if mods==3:desktop.chord(0x11,0x10,vk)
                    else:assert mods==0;desktop.chord(vk)
                else:key(vk,mods)
            def frame(name,bmp=None):
                filename=tag+'-'+name+'.png'
                (out/filename).write_bytes(api.png_from_bmp(bmp if bmp is not None else api.request(endpoint,'image',seat)))
                evidence['screenshots'].append(filename)
            ready={'opencode':'Ask anything','codex':'Ask Codex to do anything','claude':'plan mode on'}[args.client]
            if args.client=='claude':
                # A new Claude home may explicitly ask about this newly created
                # test directory. Confirm only after matching its entire path.
                screen=wait_for(lambda:s if ready in (s:=text()) or 'Yes, I trust this folder' in s else None,timeout=60)
                if ready not in screen:
                    lines=[line.strip() for line in screen.splitlines() if line.strip()]
                    begin=lines.index('Accessing workspace:')+1
                    end=next(i for i in range(begin,len(lines)) if lines[i].startswith('Quick safety check:'))
                    shown=''.join(lines[begin:end]); expected=(case/'work').resolve(strict=True)
                    assert Path(shown).resolve(strict=True)==expected and (expected/'.git').is_dir(),shown
                    if any(line.startswith('❯ No, exit') for line in lines): press(0x28)
                    wait_for(lambda:'❯ Yes, I trust this folder' in text())
                    press(13); evidence['confirmed_fixture_directory']=str(expected)
            wait_for(lambda:ready in text(),timeout=60)
            def client_trace(label):
                path=case/'client-output.log'
                if path.is_file():
                    raw=path.read_bytes(); evidence.setdefault('trace_points',[]).append(dict(
                        phase=label,seconds=time.monotonic(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
            client_trace('initial-ready');sample('startup')
            api.request(endpoint,'input',seat,SELECTION_TRIGGER)
            wait_for(lambda:SELECTION_TRIGGER in text());client_trace('trigger-visible');time.sleep(.2);press(13);client_trace('enter-sent')
            screen=wait_for(lambda:s if sample_text in (s:=text()) else None,timeout=40)
            if args.right_click:
                # Put an identifiable prefix in the composer first. The HTTP
                # fixture only accepts the exact user part (one pasted copy).
                api.request(endpoint,'input',seat,SELECTION_PREFIX)
                screen=wait_for(lambda:s if sample_text in (s:=text()) and SELECTION_PREFIX.rstrip() in s else None)
            lines=screen.split('\n');row,=[i for i,line in enumerate(lines) if sample_text in line]
            width=lambda s:sum(0 if unicodedata.combining(ch) else 2 if unicodedata.east_asian_width(ch) in ('W','F') else 1 for ch in s)
            first=width(lines[row].split(sample_text,1)[0]);last=first+width(sample_text)-1
            cols,rows=session['cols'],session['rows'];cx,cy=session['client_width'],session['client_height']
            cw,ch=(cx-2)//cols,(cy-2)//rows;ox,oy=(cx-cols*cw)//2,(cy-rows*ch)//2
            assert cw>0 and ch>0 and 0<=first<=last<cols and 0<=row<rows
            pos=lambda x:(oy+row*ch+ch//2)<<16 | (ox+x*cw+cw//2)
            assert 0<first<=last<cols-1 # include the unselected cell on each side
            evidence.update(source_line=lines[row],selection=[first,row,last],cell=[cw,ch],offset=[ox,oy])
            box=(ox+(first-1)*cw,oy+row*ch,ox+(last+2)*cw,oy+(row+1)*ch)
            def strip():
                bmp=api.request(endpoint,'image',seat)
                im=Image.open(io.BytesIO(bmp)).convert('RGB')
                assert im.size==(cx,cy)
                im=im.crop(box)
                return bmp,[list(im.crop((i*cw,0,(i+1)*cw,ch)).getdata()) for i in range(last-first+3)]
            # The client text query can lead its first completed paint. Establish
            # a stable source row with actual glyph pixels, then keep that BMP.
            prior=None;since=0
            def source_frame():
                nonlocal prior,since
                bmp,tiles=strip();now=time.monotonic()
                if tiles!=prior:prior,since=tiles,now
                if now-since>=.15 and len(set(p for tile in tiles[1:-1] for p in tile))>2:
                    return bmp,tiles
            bmp,source=wait_for(source_frame)
            frame('source',bmp);sample('reply')
            bg=Counter(p for tile in source[1:-1] for p in tile).most_common(1)[0][0]

            # Only inspect bytes already emitted by the real client. Do not
            # enable mouse modes from the harness. The full prefix is retained.
            raw=(case/'client-output.log').read_bytes()
            (out/(args.client+'-at-drag.vt')).write_bytes(raw)
            tracking=[]
            for match in re.finditer(rb'\x1b\[\?([0-9;]+)([hl])|\x1bc|\x1b\[!p',raw):
                if match[1] is None:
                    tracking.append(dict(offset=match.start(),seq=match[0].hex(),active=False));continue
                for item in match[1].split(b';'):
                    if item in (b'9',b'1000',b'1001',b'1002',b'1003'):
                        tracking.append(dict(offset=match.start(),seq=match[0].hex(),mode=int(item),active=match[2]==b'h'))
            evidence['mouse_requests_at_drag']=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),events=tracking)
            assert raw and sample_text.encode('utf-8').split(b' ')[0] in raw, 'Missing real reply in output trace'
            evidence['mouse_requests_at_drag']['active']=bool(tracking and tracking[-1]['active'])
            # OpenCode is the positive control for an app that takes the mouse.
            # Record whether Codex requested tracking; never force it on its behalf.
            if args.client=='opencode':
                assert evidence['mouse_requests_at_drag']['active'],('No active mouse request in client output',tracking)
            # A new paint may not be presented when the mouse-up call returns.
            # Check the source background in every selected cell (including the
            # spaces) and confirm it stays unchanged in both neighbouring cells.
            last_bmp=None
            def highlight_frame():
                nonlocal last_bmp
                last_bmp,after=strip()
                colours=Counter(q for a,b in zip(source[1:-1],after[1:-1])
                                for p,q in zip(a,b) if p==bg)
                if not colours:return
                target=colours.most_common(1)[0][0];ratios=[]
                for i,(a,b) in enumerate(zip(source,after)):
                    probe=[q for p,q in zip(a,b) if p==bg]
                    wanted=bg if i in (0,len(source)-1) else target
                    ratios.append(sum(q==wanted for q in probe)/len(probe) if probe else 0)
                evidence['highlight']=dict(source=bg,selected=target,cells=last-first+1,
                    min_selected_ratio=min(ratios[1:-1]),guard_ratios=[ratios[0],ratios[-1]])
                if target!=bg and min(ratios[1:-1])>=.5 and min(ratios[0],ratios[-1])>=.9:return last_bmp
            if desktop:desktop.drag(ox+first*cw+cw//2,ox+last*cw+cw//2,oy+row*ch+ch//2,highlight_frame)
            else:u.SendMessageW(hwnd,0x201,5,pos(first));u.SendMessageW(hwnd,0x200,5,pos(last));u.SendMessageW(hwnd,0x202,4,pos(last))
            try:frame('selected',wait_for(highlight_frame))
            except AssertionError:
                if last_bmp:frame('unmatched-highlight',last_bmp)
                raise
            evidence['checks'].append('visible highlight spans the selected cells and stops at both adjacent cells')
            # Replacing the clipboard with image-only data prevents auto-copy at
            # mouse-up, a prior run or the source prompt from passing Copy.
            write_snapshot(control,dict(id=1,action='bitmap'))
            wait_for(lambda:child().get('clipboard_action')==1);assert clipboard_text(hwnd) is None
            if args.right_click:
                before=u.GetClipboardSequenceNumber()
                desktop.point(ox+last*cw+cw//2,oy+row*ch+ch//2)
                desktop.chord('right')
                wait_for(lambda:u.GetClipboardSequenceNumber()!=before)
                evidence['right_click']=dict(mode=args.right_click,setting_written=args.right_click=='copy-paste',
                                             modifiers_released=not desktop.held)
            else:press(67,3)
            copied=wait_for(lambda:clipboard_text(hwnd));evidence['copied']=copied
            assert copied==sample_text,(copied,sample_text)
            sample('copy')
            if args.right_click:
                evidence['checks'].append('System right click replaced the image sentinel with exact Unicode after Shift was released')
                if args.right_click=='default':
                    assert SELECTION_PREFIX+sample_text not in text(),'default right click already pasted'
                    press(86,3)
                # Copy-and-paste must fill the composer without any paste key.
            else:
                evidence['checks'].append('Shift drag and default Copy replace the sentinel with exact Unicode')
                api.request(endpoint,'input',seat,SELECTION_PREFIX)
                wait_for(lambda:SELECTION_PREFIX.rstrip() in text());press(86,3)
            # The real Claude composer can draw a precomposed accent even
            # though the clipboard contained the original combining sequence.
            # Observe both spellings in the UI; the subsequent HTTP assertion
            # checks the digest of the exact independently expected user part.
            expected_prompt=SELECTION_PREFIX+sample_text
            ref=claude_reference(observed['client_sha256']) if args.client=='claude' and not args.stable_unicode else None
            if ref:evidence['independent_client_reference']=ref
            http_text=unicodedata.normalize('NFC',expected_prompt) if ref else expected_prompt
            want_hash=hashlib.sha256(http_text.encode()).hexdigest()
            def composer_form():
                view=text()
                if expected_prompt in view:return 'exact'
                if ref and unicodedata.normalize('NFC',expected_prompt) in view:return 'NFC'
            evidence['composer_form']=wait_for(composer_form,timeout=20)
            frame('composer');sample('composer')
            time.sleep(.2);press(13)
            # read_snapshot returns {} on a transient Windows sharing violation.
            # Require the positive provider receipt from one complete snapshot.
            evidence['unavailable_http_snapshots']=0
            def submitted():
                snapshot=child()
                if 'requests' not in snapshot:
                    evidence['unavailable_http_snapshots']+=1
                    return None
                return next((r for r in snapshot['requests'] if r.get('fixture_prompt_hashes')==[want_hash]
                             and (r['selection_nfc_present'] and not r['selection_received'] if ref else
                                  r['selection_received'] and r['selected_text_occurrences']==1)
                             and r['text'].count('NEMOTERM_SUBMIT')==1 and r['text'].count('NEMOTERM_SELECT')==1 and r['path']==
                             {'codex':'/v1/responses','opencode':'/v1/chat/completions','claude':'/v1/messages'}[args.client]),None)
            evidence['http_receipt']=wait_for(submitted,timeout=30)
            wait_for(lambda:'NEMOTERM_TEXT_ACCEPTED' in text());evidence['checks'].append('submitted prompt matched the two independent client references' if ref else f'real {args.client} submitted the exact original prompt')
            sample('submitted')
            if sampler:
                stop.set();sampler.join(5)
                assert not sampler.is_alive() and not sample_errors and len(samples)>=2,(len(samples),sample_errors)
                assert all(private_ws_passes(actual,v['private_ws']) for v in samples),max(samples,key=lambda x:x['private_ws'])
            evidence['memory_policy']=private_ws_policy(actual)
            assert all(private_ws_passes(actual,v['private_ws']) for v in evidence['frontend_samples']),evidence['frontend_samples']
            write_snapshot(control,dict(id=2,action='restore'));wait_for(lambda:child().get('clipboard_restored'))
            evidence['exit_keys']=[]
            for index in range(2):
                if proc.poll() is not None or not u.IsWindow(hwnd):break
                try:
                    if desktop:desktop.chord(0x11,67)
                    else:key(67,2)
                except (OSError,EOFError):break
                evidence['exit_keys'].append(dict(index=index,system=bool(desktop)))
                time.sleep(.2)
            assert proc.wait(timeout=20)==0
            observed=read_snapshot(report);assert not observed['errors'] and not observed['cleanup']['terminated_remaining'],observed
            evidence['completed']=True
        except BaseException:
            evidence['error']=traceback.format_exc()
            if endpoint and seat:
                try:
                    evidence['last_screen']=text();frame('failure')
                except Exception:pass
            raise
        finally:
            trace=case/'client-output.log'
            if trace.is_file():
                raw=trace.read_bytes();name=tag+'-client-output.vt';(out/name).write_bytes(raw)
                evidence['client_output']=dict(file=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            if desktop:desktop.restore()
            if sampler:
                stop.set();sampler.join(5)
                evidence['frontend_trace']=dict(samples=samples,errors=sample_errors,start='session discovered',stop='after submitted reply or failure',requested_interval_ms=100)
            if handle:k.CloseHandle(handle)
            if proc.poll() is None:
                write_snapshot(control,dict(id=99,action='finish'))
                try:proc.wait(timeout=15)
                except subprocess.TimeoutExpired:pass
            evidence['cleanup']=job.finish();evidence['child']=read_snapshot(report)
            write_snapshot(out/(tag+'-observed.json'),evidence)


if __name__=='__main__':main()
