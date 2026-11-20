"""Use real hosted mouse/keyboard input on the tab bar, without a debugger or injected hooks."""
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from PIL import Image
from clipboard_test_utils import SavedClipboard, clipboard_text
from fixture_io import read_snapshot, wait_snapshot, write_snapshot
from hosted_gesture_input import DesktopInput
from native_test_utils import c, w, u, root, find_window, terminal_host, wait_for
from owned_job import OwnedJob
from presented_window_capture import PresentedWindowCapture
from protocol_oracle_window import saved_profile

SIDES = ('top', 'bottom', 'left', 'right')
ACK = b'\x1b[0n'
RED, BLUE, GREEN = (228, 30, 36), (25, 40, 226), (28, 214, 60)
u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE
u.GetDpiForWindow.argtypes = [w.HWND]
u.FindWindowExW.argtypes, u.FindWindowExW.restype = [w.HWND, w.HWND, w.LPCWSTR, w.LPCWSTR], w.HWND


def rect(hwnd):
    r = w.RECT(); assert u.GetClientRect(hwnd, c.byref(r)); return r


def label(side, host):
    r = rect(host); dpi = u.GetDpiForWindow(host); assert dpi > 0
    row, sidebar = [(n*dpi+48)//96 for n in (28, 192)]
    x, y = {'top': (20, row//2), 'bottom': (20, r.bottom-row//2),
            'left': (sidebar//2, row//2), 'right': (r.right-sidebar//2, row//2)}[side]
    p = w.POINT(x, y); assert u.ClientToScreen(host, c.byref(p)); return p


def perform(side, exe, tmp, out, profile, job, rec):
    proc = job.spawn([str(exe), *profile, '--tabs', '--tab-side', side, '-e', sys.executable,
                      str(root/'tests/session_fixture.py'), str(tmp), '120'],
                     env=dict(os.environ, NEMOTERM_CONPTY='bundled', NEMOTERM_TEST_INPUT_CP='65001',
                              NEMOTERM_TEST_EXACT_OUTPUT='1'), creationflags=subprocess.CREATE_NO_WINDOW)
    rec['pid'] = proc.pid; views = []; children = []; expected = [ACK, ACK]; controls = [{}, {}]
    desk = saved = None
    def file(i, kind): return tmp/f'{children[i]}.{kind}.json'
    def draw(i, colour, phase):
        style = ';'.join(map(str, colour)); text = 'Copy7' if i == 0 else 'Other'
        patch = ''.join(f'\x1b[{row};2H'+(' '*32) for row in range(5, 14))
        seq = (f'\x1b[?25l\x1b[2J\x1b[3;1H|{text}|\x1b[48;2;{style}m'+patch+
               '\x1b[0m\x1b[?1002;1006h\x1b[5n')
        controls[i] = dict(phase=phase, sequence=seq)
        write_snapshot(file(i,'control'), controls[i]); expected[i] = ACK
        return wait_snapshot(lambda:read_snapshot(file(i,'report')), lambda v:v.get('phase')==phase and v.get('hex')==ACK.hex())
    def barrier(serial, delta):
        row = []; rec.setdefault('input', []).append(row)
        # SendInput returns when the key is queued, not when the terminal has
        # dispatched it. The children's independently written DSRs must follow
        # its delivery. Keep the original exact byte/order checks on both tabs.
        before = []; rec.setdefault('before_input_barrier', []).append(before)
        for i, key in enumerate(delta):
            if key:
                want = (expected[i]+key).hex()
                snapshot = wait_snapshot(lambda:read_snapshot(file(i,'report')),
                    lambda v:v.get('phase')==controls[i]['phase'] and v.get('hex')==want)
                before.append(dict(pid=children[i], serial=serial, expected=want, actual=snapshot['hex']))
        for i in range(2):
            controls[i]['input_barrier'] = serial; write_snapshot(file(i,'control'), controls[i]); expected[i] += delta[i]+ACK
            r = wait_snapshot(lambda:read_snapshot(file(i,'report')), lambda v:v.get('input_barrier')==serial)
            row.append(dict(pid=children[i],expected=expected[i].hex(),actual=r['hex'])); assert r['hex']==expected[i].hex(),row
    def owned_popup():
        win = None
        while win := u.FindWindowExW(None, win, 'NemotermPreview', None):
            if desk.u.GetWindow(win, 4)==host and u.IsWindowVisible(win):return win
    def active(i):
        return find_window(proc.pid)==views[i] and desk.state().focus==views[i] and desk.u.GetForegroundWindow()==host
    try:
        for i, colour in enumerate((RED, GREEN)):
            rec['phase'] = f'open-tab-{i}'
            if i: u.SendMessageW(views[0], 0x111, 0x30, 0)  # Duplicate session; share the test application, not its mailbox.
            def new_pid():
                return next((v['pid'] for f in tmp.glob('*.launch.json') if (v:=read_snapshot(f)).get('parent')==proc.pid and v['pid'] not in children),None)
            children.append(wait_for(new_pid)); views.append(wait_for(lambda:h if (h:=find_window(proc.pid)) and h not in views else None))
            host = terminal_host(views[0]); assert host!=views[0] and terminal_host(views[i])==host
            draw(i, colour, 1)
        rec.update(children=children, views=views, host=host)
        def renderer(i):
            val = int(u.GetPropW(views[i], 'NemotermRenderer') or 0); assert val in (1, 2),val
            return {1:'GDI fallback',2:'OpenGL'}[val]
        rec['second_renderer']=renderer(1)
        desk = DesktopInput(proc.pid, host, views[1], rec.setdefault('desktop',{})); saved = SavedClipboard(views[0]); assert active(1)
        rec['phase'] = 'hover-hidden-tab'; point = label(side, host)
        # Start from content so Windows delivers an actual enter even if the pointer was already on the label.
        desk.point(rect(views[1]).right//2, rect(views[1]).bottom//2)
        desk.move_screen(point.x, point.y)
        def on_label():
            p=w.POINT(); assert desk.u.GetCursorPos(c.byref(p)); return (p.x,p.y)==(point.x,point.y) and desk.u.WindowFromPoint(p)==host
        wait_for(on_label); popup = wait_for(owned_popup); capture=PresentedWindowCapture(proc.pid,popup,raise_window=False)
        def expect_colour(name, colour):
            rec['phase']=name; counts=rec.setdefault('pixels',{})
            def sample():
                bmp=capture.capture(); im=Image.open(io.BytesIO(bmp)).convert('RGB')
                assert 0<im.width<=320 and 0<im.height<=200,(im.width,im.height)
                palette=dict((rgb,n) for n,rgb in im.getcolors(im.width*im.height)); counts[name]=[palette.get(rgb,0) for rgb in (RED,BLUE,GREEN)]
                if palette.get(colour,0)>=128 and all(palette.get(k,0)==0 for k in (RED,BLUE,GREEN) if k!=colour):
                    im.save(out/(name+'.png')); return True
                return False
            try:wait_for(sample)
            except Exception:
                (out/(name+'-last.bmp')).write_bytes(capture.capture()); raise
            assert active(1) and on_label()
        try:
            expect_colour('initial-preview',RED)
            draw(0,BLUE,2); expect_colour('updated-preview',BLUE)
            desk.chord(ord('7')); barrier(1,(b'',b'7')); assert active(1) and owned_popup()==popup
        finally: rec['capture']=capture.close()
        rec['phase']='click-previewed-tab'; assert on_label(); desk.event(None,True); desk.event(None,False)
        wait_for(lambda:active(0) and not owned_popup()); desk.hwnd=views[0]; desk.target(); rec['first_renderer']=renderer(0)
        desk.chord(ord('8')); barrier(2,(b'8',b''))
        rec['phase']='select-and-copy'; r=rect(views[0]); state=read_snapshot(file(0,'report'))
        cw, dx=divmod(r.right-2,state['columns']); ch, dy=divmod(r.bottom-2,state['rows'])
        rec['grid']=[state['columns'],state['rows'],r.right,r.bottom,cw,ch,dx,dy]; assert not(dx or dy) and min(cw,ch)>0,rec['grid']
        y=1+2*ch+ch//2; desk.point(1+cw+cw//2,y); desk.event(0x10,True); desk.event(None,True)
        wait_for(lambda:desk.state().capture==views[0]); desk.point(1+5*cw+cw//2,y); desk.event(None,False); desk.event(0x10,False)
        wait_for(lambda:not desk.state().capture); old=u.GetClipboardSequenceNumber(); desk.chord(0x11,0x10,ord('C'))
        rec['copied']=wait_for(lambda:v if u.GetClipboardSequenceNumber()!=old and (v:=clipboard_text(views[0]))=='Copy7' else None)
        barrier(3,(b'',b'')); rec['phase']='close'; saved.restore(); saved=None; desk.restore(); desk=None
        for i in (0,1):
            write_snapshot(file(i,'control'),dict(stop=True)); wait_snapshot(lambda:read_snapshot(file(i,'exit')),lambda v:v.get('reason')=='control-stop')
        assert proc.wait(timeout=12)==0
    finally:
        rec['frontend_exit_before_cleanup']=proc.poll()
        if saved:saved.restore()
        if desk:desk.restore()


if __name__=='__main__':
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise SystemExit('Hosted desktop required')
    exe=Path(os.environ['NEMOTERM_TEST_EXE']); sha=hashlib.sha256(exe.read_bytes()).hexdigest(); failures=[]
    for side in ('right','top','bottom','left'):
        out=root/'research'/'tab-hover-native'/side; out.mkdir(parents=True,exist_ok=True)
        font=os.environ['NEMOTERM_TEST_FONT']; rec=dict(side=side, requested_renderer='OpenGL', completed=False, executable_sha256=sha, font=font)
        try:
            with tempfile.TemporaryDirectory() as tmp, saved_profile(dict(NemoTabs=1,NemoRenderer=1,NemoTabPreview=1,NemoTabSide=SIDES.index(side),Font=font,FontHeight=10,TermWidth=60,TermHeight=20,WarnOnClose=0,CloseOnExit=1,ScrollBar=0,WindowBorder=1)) as profile, OwnedJob() as job:
                try:perform(side,exe,Path(tmp),out,profile,job,rec)
                finally: rec['cleanup']=job.finish()
                assert not rec['cleanup']['terminated_remaining']; rec.update(phase='complete',completed=True)
        except Exception:
            rec['error']=traceback.format_exc(); failures.append(side); print(rec['error'],flush=True)
        finally:(out/'result.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8')
    if failures:raise SystemExit('Failed sides: '+', '.join(failures))
