"""Tab middle-button ownership on an actual GitHub-hosted Windows desktop."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from fixture_io import read_snapshot, wait_snapshot, write_snapshot
from hosted_gesture_input import DesktopInput
from native_test_utils import c, w, u, root, find_window, terminal_host, wait_for
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile
from tab_hover_native import SIDES, rect
sys.path.insert(0,str(root/'tools'))
import nemoterm_debug as api


def run(side, case, exe, tmp, profile, job, record):
    proc=job.spawn([str(exe), *profile, '--tabs', '--automation', '--tab-side', side,
                    '-e', sys.executable, str(root/'tests/session_fixture.py'), str(tmp), '120'],
                   creationflags=subprocess.CREATE_NO_WINDOW, env=dict(os.environ,NEMOTERM_CONPTY='bundled'))
    host=desk=None; children=[]; views=[]
    try:
        endpoint=wait_for(lambda:next(iter(api.discover(proc.pid)),{}).get('endpoint'))
        def sessions(): return api.request(endpoint)['sessions']
        for i in range(2):
            if i: u.SendMessageW(views[0],0x111,0x30,0)  # Duplicate the test application into a distinct session.
            def new_pid():return next((r['pid'] for f in tmp.glob('*.launch.json') if (r:=read_snapshot(f)).get('parent')==proc.pid and r['pid'] not in children),None)
            pid=wait_for(new_pid); children.append(pid)
            hwnd=wait_for(lambda:h if (h:=find_window(proc.pid)) and h not in views else None); views.append(hwnd)
            write_snapshot(tmp/f'{pid}.control.json',dict(phase=1,sequence='\x1b[5n'))
            wait_snapshot(lambda:read_snapshot(tmp/f'{pid}.report.json'),lambda r:r.get('hex')=='1b5b306e')
        host=terminal_host(views[1]); desk=DesktopInput(proc.pid,host,views[1],record.setdefault('desktop',{}))
        def inventory():
            if proc.poll() is not None:return []
            try:return sorted((s['hwnd'],s['active']) for s in sessions())
            except OSError:
                try:proc.wait(timeout=.5)
                except subprocess.TimeoutExpired:raise
                return []
        before=inventory();assert before==sorted([(views[0],False),(views[1],True)]);record.update(before=before,views=views,children=children)
        def move(where):
            r=rect(host); dpi=u.GetDpiForWindow(host);row,sidebar,preferred=[(v*dpi+48)//96 for v in (28,192,168)]
            vertical=side in ('left','right'); length=r.bottom if vertical else r.right
            extent=row if vertical else min(preferred,(length-row)//2)
            p=length-row//2 if where=='plus' else extent*(where=='B')+extent//3
            x,y={'top':(p,row//2),'bottom':(p,r.bottom-row//2),'left':(sidebar//2,p),'right':(r.right-sidebar//2,p)}[side]
            dest=w.POINT(x,y);assert u.ClientToScreen(host,c.byref(dest));desk.move_screen(dest.x,dest.y)
            def arrived():
                actual=w.POINT();assert desk.u.GetCursorPos(c.byref(actual));return (actual.x,actual.y)==(dest.x,dest.y) and desk.u.WindowFromPoint(actual)==host
            wait_for(arrived);record.setdefault('positions',[]).append([where,dest.x,dest.y]);desk.target()
        def input_seen(key, suffix):
            desk.chord(ord(key));r=wait_snapshot(lambda:read_snapshot(tmp/f'{children[1]}.report.json'),lambda v:v.get('hex','').endswith(suffix.encode().hex()))
            record.setdefault('active_input',[]).append(r['hex'])
        record['phase']='middle-down'; move('plus' if case=='plus' else 'A'); desk.event('middle',True)
        # An input-queue witness before changing layout or injecting cancellation.
        # The focused terminal must still be B after pressing an inactive label.
        input_seen('3','3');record['capture_at_press']=desk.state().capture
        if case=='cross':move('B')
        elif case=='cancel':u.SendMessageW(host,0x001F,0,0)  # WM_CANCELMODE
        elif case=='tab-exits':
            write_snapshot(tmp/f'{children[0]}.control.json',dict(stop=True))
            wait_for(lambda:inventory()==[(views[1],True)]);move('A') # B now occupies A's slot.
        record['phase']='middle-up'; desk.event('middle',False)
        expected=sorted([(views[1],True)] if case in ('click','tab-exits') else before);record['expected']=expected
        # A close is posted, not synchronous. Collect transitions instead of
        # accepting a still-unchanged first sample as proof of a cancelled drag.
        states=record['after_release']=[]; deadline=time.monotonic()+2
        while True:
            current=inventory()
            if not states or states[-1]!=current:states.append(current)
            if case=='click' and current==expected:break
            if time.monotonic()>=deadline:break
            time.sleep(.025)
        assert current==expected,(case,current,expected)
        wait_for(lambda:desk.state().focus==views[1] and not desk.state().capture);input_seen('4','34')
        assert inventory()==expected
        record['completed_gesture']=True
    finally:
        if desk:desk.restore()
        if host and u.IsWindow(host):u.PostMessageW(host,0x10,0,0)
        if host:record['frontend_exit']=proc.wait(timeout=12)


if __name__=='__main__':
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise SystemExit('Hosted desktop required')
    exe=Path(os.environ['NEMOTERM_TEST_EXE']);sha=hashlib.sha256(exe.read_bytes()).hexdigest();failures=[]
    for i,side in enumerate(SIDES):
        for case in ('click','cross','plus','cancel','tab-exits'):
            out=root/'research'/'tab-hover-native'/side/'middle';out.mkdir(parents=True,exist_ok=True)
            rec=dict(completed=False,side=side,case=case,sha256=sha)
            try:
                with tempfile.TemporaryDirectory() as tmp,saved_profile(dict(NemoTabs=1,NemoTabSide=i,Font=os.environ['NEMOTERM_TEST_FONT'],FontHeight=10,TermWidth=60,TermHeight=20,WarnOnClose=0,CloseOnExit=1)) as profile, OwnedJob() as job:
                    try:run(side,case,exe,Path(tmp),profile,job,rec)
                    finally:rec['cleanup']=job.finish()
                    assert rec['frontend_exit']==0 and not rec['cleanup']['terminated_remaining'];rec['completed']=True
            except Exception:rec['error']=traceback.format_exc();failures.append((side,case));print(rec['error'],flush=True)
            finally:(out/(case+'.json')).write_text(json.dumps(rec,indent=2),encoding='utf-8')
    if failures:raise SystemExit(f'Failed gestures: {failures}')
