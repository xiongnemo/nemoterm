"""Shift-select a real OpenCode reply in a DirectX tab and submit the copied text."""
import argparse
import os
import struct
import subprocess
import sys
import tempfile
import time
import traceback
import unicodedata
from pathlib import Path

from agent_clipboard_fixture import SELECTION_PREFIX, SELECTION_TEXT, SELECTION_TRIGGER
from clipboard_test_utils import clipboard_text
from fixture_io import read_snapshot, write_snapshot
from native_test_utils import u, w, c, wait_for
from owned_job import OwnedJob

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import nemoterm_debug as api


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise SystemExit('OpenCode interaction requires a GitHub-hosted runner')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client-exe',required=True)
    parser.add_argument('--font',required=True)
    args=parser.parse_args()
    out=ROOT/'research';out.mkdir(exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='opencode-selection-',dir=ROOT/'build'))
    case=folder/'client'; report=case/'observed.json'; control=case/'control.json'
    evidence=dict(completed=False,font=args.font,checks=[],screenshots=[],global_input=False)
    with OwnedJob() as job,(folder/'fixture.log').open('w',encoding='utf-8') as log:
        proc=job.spawn([sys.executable,str(ROOT/'tests/agent_clipboard_fixture.py'),
            '--client','opencode','--client-exe',str(Path(args.client_exe).resolve()),
            '--terminal',os.environ['NEMOTERM_TEST_EXE'],'--directory',str(case),
            '--automation','--selection-directx','--font',args.font],stdout=log,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
        def child():
            value=read_snapshot(report);assert proc.poll() is None and not value.get('errors'),value
            return value
        endpoint=seat=None
        try:
            observed=wait_for(child,timeout=40)
            instance=wait_for(lambda: next(iter(api.discover(observed['pid'])),None),timeout=20)
            endpoint=instance['endpoint'];session,=instance['sessions'];seat=session['id'];hwnd=session['hwnd']
            evidence['session']=session
            assert instance['pid']==observed['pid'] and hwnd==observed['hwnd'] and session['active'] and session['renderer']==2,session
            assert hwnd!=session['window'],'Expected the default multi-tab host'
            text=lambda:api.request(endpoint,'text',seat)
            def key(vk,mods=0):api.request(endpoint,'key',seat,struct.pack('<II',vk,mods))
            def frame(name):
                filename='opencode-selection-'+name+'.png'
                (out/filename).write_bytes(api.png_from_bmp(api.request(endpoint,'image',seat)))
                evidence['screenshots'].append(filename)
            wait_for(lambda:'Ask anything' in text(),timeout=60)
            api.request(endpoint,'input',seat,SELECTION_TRIGGER)
            wait_for(lambda:SELECTION_TRIGGER in text());time.sleep(.2);key(13)
            screen=wait_for(lambda:s if SELECTION_TEXT in (s:=text()) else None,timeout=40)
            lines=screen.split('\n');row,=[i for i,line in enumerate(lines) if SELECTION_TEXT in line]
            width=lambda s:sum(0 if unicodedata.combining(ch) else 2 if unicodedata.east_asian_width(ch) in ('W','F') else 1 for ch in s)
            first=width(lines[row].split(SELECTION_TEXT,1)[0]);last=first+width(SELECTION_TEXT)-1
            cols,rows=session['cols'],session['rows'];cx,cy=session['client_width'],session['client_height']
            cw,ch=(cx-2)//cols,(cy-2)//rows;ox,oy=(cx-cols*cw)//2,(cy-rows*ch)//2
            assert cw>0 and ch>0 and 0<=first<=last<cols and 0<=row<rows
            pos=lambda x:(oy+row*ch+ch//2)<<16 | (ox+x*cw+cw//2)
            evidence.update(source_line=lines[row],selection=[first,row,last],cell=[cw,ch],offset=[ox,oy]);frame('source')
            u.SendMessageW(hwnd,0x201,5,pos(first));u.SendMessageW(hwnd,0x200,5,pos(last));u.SendMessageW(hwnd,0x202,4,pos(last))
            frame('selected')
            # Replacing the clipboard with image-only data prevents auto-copy at
            # mouse-up, a prior run or the source prompt from passing Copy.
            write_snapshot(control,dict(id=1,action='bitmap'))
            wait_for(lambda:child().get('clipboard_action')==1);assert clipboard_text(hwnd) is None
            key(67,3);copied=wait_for(lambda:clipboard_text(hwnd));evidence['copied']=copied
            assert copied==SELECTION_TEXT,(copied,SELECTION_TEXT)
            evidence['checks'].append('Shift drag and default Copy replace the sentinel with exact Unicode')
            api.request(endpoint,'input',seat,SELECTION_PREFIX)
            wait_for(lambda:SELECTION_PREFIX.rstrip() in text());key(86,3)
            wait_for(lambda:SELECTION_PREFIX+SELECTION_TEXT in text(),timeout=20);frame('composer')
            time.sleep(.2);key(13)
            wait_for(lambda:any(r['selection_received'] for r in child()['requests']),timeout=30)
            wait_for(lambda:'NEMOTERM_TEXT_ACCEPTED' in text());evidence['checks'].append('real OpenCode submitted exact combined prompt to the loopback provider')
            write_snapshot(control,dict(id=2,action='restore'));wait_for(lambda:child().get('clipboard_restored'))
            for _ in range(2):
                try:key(67,2)
                except (OSError,EOFError):break
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
            if proc.poll() is None:
                write_snapshot(control,dict(id=99,action='finish'))
                try:proc.wait(timeout=15)
                except subprocess.TimeoutExpired:pass
            evidence['cleanup']=job.finish();evidence['child']=read_snapshot(report)
            write_snapshot(out/'opencode-selection-observed.json',evidence)


if __name__=='__main__':main()
