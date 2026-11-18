"""Shift-select a real OpenCode reply in an actual GDI or DirectX tab and submit the copied text."""
import argparse
from collections import Counter
import io
import os
import re
import hashlib
import struct
import subprocess
import sys
import tempfile
import time
import traceback
import unicodedata
from pathlib import Path
from PIL import Image

from agent_clipboard_fixture import SELECTION_PREFIX, SELECTION_TEXT, SELECTION_TRIGGER
from clipboard_test_utils import clipboard_text
from fixture_io import read_snapshot, write_snapshot
from native_test_utils import u, k, wait_for, memory_sample
from memory_limits import private_ws_policy, private_ws_passes
from owned_job import OwnedJob
from frontend_runtime_snapshot import snapshot as runtime_snapshot

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import nemoterm_debug as api


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise SystemExit('OpenCode interaction requires a GitHub-hosted runner')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client-exe',required=True)
    parser.add_argument('--font',required=True)
    parser.add_argument('--renderer',choices=('gdi','directx'),required=True)
    parser.add_argument('--system-input',action='store_true')
    parser.add_argument('--right-click',choices=('default','copy-paste'))
    args=parser.parse_args()
    assert not args.right_click or args.system_input
    out=ROOT/'research';out.mkdir(exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='opencode-selection-',dir=ROOT/'build'))
    case=folder/'client'; report=case/'observed.json'; control=case/'control.json'
    tag='opencode-selection-'+args.renderer+('-system' if args.system_input else '')
    if args.right_click:tag+='-right-'+args.right_click
    evidence=dict(completed=False,font=args.font,requested_renderer=args.renderer,checks=[],screenshots=[],global_input=args.system_input,frontend_samples=[])
    with OwnedJob() as job,(folder/'fixture.log').open('w',encoding='utf-8') as log:
        proc=job.spawn([sys.executable,str(ROOT/'tests/agent_clipboard_fixture.py'),
            '--client','opencode','--client-exe',str(Path(args.client_exe).resolve()),
            '--terminal',os.environ['NEMOTERM_TEST_EXE'],'--directory',str(case),
            '--automation','--selection-renderer',args.renderer,'--font',args.font]+
            (['--right-copy-and-paste'] if args.right_click=='copy-paste' else []),stdout=log,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
        def child():
            value=read_snapshot(report);assert proc.poll() is None and not value.get('errors'),value
            return value
        endpoint=seat=handle=desktop=None
        try:
            observed=wait_for(child,timeout=40)
            instance=wait_for(lambda: next(iter(api.discover(observed['pid'])),None),timeout=20)
            endpoint=instance['endpoint'];session,=instance['sessions'];seat=session['id'];hwnd=session['hwnd']
            evidence['session']=session
            assert instance['pid']==observed['pid'] and hwnd==observed['hwnd'] and session['active'] and session['renderer']=={'gdi':0,'directx':2}[args.renderer],session
            assert hwnd!=session['window'],'Expected the default multi-tab host'
            handle=k.OpenProcess(0x0410,False,observed['pid']);assert handle
            actual=session['renderer']+1
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
            wait_for(lambda:'Ask anything' in text(),timeout=60)
            sample('startup')
            api.request(endpoint,'input',seat,SELECTION_TRIGGER)
            wait_for(lambda:SELECTION_TRIGGER in text());time.sleep(.2);press(13)
            screen=wait_for(lambda:s if SELECTION_TEXT in (s:=text()) else None,timeout=40)
            if args.right_click:
                # Put an identifiable prefix in the composer first. The HTTP
                # fixture only accepts the exact user part (one pasted copy).
                api.request(endpoint,'input',seat,SELECTION_PREFIX)
                screen=wait_for(lambda:s if SELECTION_TEXT in (s:=text()) and SELECTION_PREFIX.rstrip() in s else None)
            lines=screen.split('\n');row,=[i for i,line in enumerate(lines) if SELECTION_TEXT in line]
            width=lambda s:sum(0 if unicodedata.combining(ch) else 2 if unicodedata.east_asian_width(ch) in ('W','F') else 1 for ch in s)
            first=width(lines[row].split(SELECTION_TEXT,1)[0]);last=first+width(SELECTION_TEXT)-1
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
            (out/'opencode-at-drag.vt').write_bytes(raw)
            tracking=[]
            for match in re.finditer(rb'\x1b\[\?([0-9;]+)([hl])|\x1bc|\x1b\[!p',raw):
                if match[1] is None:
                    tracking.append(dict(offset=match.start(),seq=match[0].hex(),active=False));continue
                for item in match[1].split(b';'):
                    if item in (b'9',b'1000',b'1001',b'1002',b'1003'):
                        tracking.append(dict(offset=match.start(),seq=match[0].hex(),mode=int(item),active=match[2]==b'h'))
            evidence['mouse_requests_at_drag']=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),events=tracking)
            assert tracking and tracking[-1]['active'],('No active mouse request in the recorded client output',tracking)
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
            assert copied==SELECTION_TEXT,(copied,SELECTION_TEXT)
            sample('copy')
            if args.right_click:
                evidence['checks'].append('System right click replaced the image sentinel with exact Unicode after Shift was released')
                if args.right_click=='default':
                    assert SELECTION_PREFIX+SELECTION_TEXT not in text(),'default right click already pasted'
                    press(86,3)
                # Copy-and-paste must fill the composer without any paste key.
            else:
                evidence['checks'].append('Shift drag and default Copy replace the sentinel with exact Unicode')
                api.request(endpoint,'input',seat,SELECTION_PREFIX)
                wait_for(lambda:SELECTION_PREFIX.rstrip() in text());press(86,3)
            wait_for(lambda:SELECTION_PREFIX+SELECTION_TEXT in text(),timeout=20);frame('composer');sample('composer')
            time.sleep(.2);press(13)
            # read_snapshot returns {} on a transient Windows sharing violation.
            # Require the positive provider receipt from one complete snapshot.
            evidence['unavailable_http_snapshots']=0
            def submitted():
                snapshot=child()
                if 'requests' not in snapshot:
                    evidence['unavailable_http_snapshots']+=1
                    return None
                return next((r for r in snapshot['requests'] if r['selection_received']
                             and r['selected_text_occurrences']==1),None)
            evidence['http_receipt']=wait_for(submitted,timeout=30)
            wait_for(lambda:'NEMOTERM_TEXT_ACCEPTED' in text());evidence['checks'].append('real OpenCode submitted exact combined prompt to the loopback provider')
            sample('submitted')
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
            if desktop:desktop.restore()
            if handle:k.CloseHandle(handle)
            if proc.poll() is None:
                write_snapshot(control,dict(id=99,action='finish'))
                try:proc.wait(timeout=15)
                except subprocess.TimeoutExpired:pass
            evidence['cleanup']=job.finish();evidence['child']=read_snapshot(report)
            write_snapshot(out/(tag+'-observed.json'),evidence)


if __name__=='__main__':main()
