"""Exercise the actual fullscreen hot pixel and its neighbour on a hosted desktop."""
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops
from clipboard_test_utils import SavedClipboard, clipboard_text, set_clipboard
from fixture_io import read_snapshot, wait_snapshot, write_snapshot
from hosted_gesture_input import DesktopInput
from native_test_utils import c, w, u, root, find_window, terminal_host, wait_for
from owned_job import OwnedJob
from presented_window_capture import PresentedWindowCapture
from protocol_oracle_window import saved_profile

CSI = '\x1b['
ACK = b'\x1b[0n'
LABEL = 'A\u4e2dZ'
BG = (24, 64, 96)


def run(engine, dest, record):
    assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
    exe = Path(os.environ['NEMOTERM_TEST_EXE']).resolve()
    font = os.environ['NEMOTERM_TEST_FONT']
    record.update(sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), font=font)
    with tempfile.TemporaryDirectory() as folder, OwnedJob() as job, saved_profile(dict(NemoRenderer=engine-1, WarnOnClose=0)) as profile:
        control, report = (Path(folder)/n for n in ('control','report'))
        proc = job.spawn([str(exe), *profile, '--no-tabs', '--font', font, '--cols','60','--rows','16', '-e', sys.executable,
                          str(root/'tests/mouse_fixture.py'),str(report),str(control),'100'],
                         env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1',NEMOTERM_TEST_INPUT_CP='65001',NEMOTERM_TEST_WIDE_INPUT='1'),creationflags=subprocess.CREATE_NO_WINDOW)
        hwnd = wait_for(lambda:find_window(proc.pid)); assert terminal_host(hwnd)==hwnd
        wait_snapshot(lambda:read_snapshot(report))
        u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
        record['renderer']=u.GetPropW(hwnd,'NemotermRenderer'); assert record['renderer']==engine
        desktop=surface=None; saved=SavedClipboard(hwnd)
        try:
            desktop=DesktopInput(proc.pid,hwnd,hwnd,record.setdefault('desktop',{}))
            def phase(name, sequence):
                req=dict(phase=name,sequence=sequence+CSI+'5n');write_snapshot(control,req)
                v=wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('phase')==name and bytes.fromhex(v['hex']).endswith(ACK))
                return req,bytes.fromhex(v['hex'])
            def drain(req):
                write_snapshot(control,dict(req,input_barrier=req['phase']))
                v=wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('input_barrier')==req['phase'])
                return bytes.fromhex(v['hex'])
            phase('fullscreen',CSI+'10;1t')
            # This runner is single-monitor. Confirm the actual HWND fills that monitor
            # and its client owns the hot pixel before testing any gestures there.
            width,height=(desktop.u.GetSystemMetrics(i) for i in (0,1))
            def covers():
                r=w.RECT();p=w.POINT();assert u.GetWindowRect(hwnd,c.byref(r)) and u.ClientToScreen(hwnd,c.byref(p))
                return (r.left,r.top,r.right,r.bottom,p.x,p.y)==(0,0,width,height,0,0) and not u.GetWindowLongW(hwnd,-16)&0xc00000
            wait_for(covers);record['monitor']=[0,0,width,height]
            surface=PresentedWindowCapture(proc.pid,hwnd,engine==3,raise_window=False);surface.wait_for_initial_geometry()
            seq=CSI+'?25l'+CSI+'2J'+CSI+'H'+CSI+'48;2;24;64;96m'+LABEL+CSI+'0m!'+CSI+'?1002;1006;2004h'+CSI+'16t'
            req,raw=phase('paint',seq); h,cw=map(int,re.fullmatch(rb'\x1b\[6;(\d+);(\d+)t'+re.escape(ACK),raw).groups())
            def shot():
                with Image.open(io.BytesIO(surface.capture())) as im:return im.crop((0,0,min(20*cw,width),min(h*4,height))).convert('RGB')
            def line():
                im=shot(); points=[(x,y) for y in range(im.height) for x in range(im.width) if im.getpixel((x,y))==BG]
                if not points:return
                xs,ys=zip(*points); box=(min(xs),min(ys),max(xs)+1,max(ys)+1)
                if box[2]-box[0]==4*cw and box[3]-box[1]==h:return im,box
            before,(ox,oy,x1,y1)=wait_for(line);before.save(dest/'before.png');record['ink_box']=[ox,oy,x1,y1]
            y=oy+h//2; end=ox+3*cw+cw//2
            # A nearby ordinary left click must reach the real child as two SGR mouse reports.
            desktop.point(end,y);desktop.chord(None)
            wait_snapshot(lambda:read_snapshot(report),lambda v:bytes.fromhex(v.get('hex','')).endswith(b'm'))
            nearby=drain(req);record['nearby_wire']=nearby.hex()
            assert nearby==raw+b'\x1b[<0;4;1M\x1b[<0;4;1m'+ACK,nearby
            # Observe ownership while down. Menu mode is per GUI thread; it is distinct
            # from capture by the terminal itself and from the cursor merely reaching it.
            def press(shift):
                desktop.point(0,0)
                if shift:desktop.event(0x10,True)
                desktop.event(None,True)
                def observed():
                    s=desktop.state();menu=bool(s.flags & 0x1c or s.menu);capture=s.capture==hwnd
                    state=dict(menu=menu,terminal_capture=capture,flags=s.flags,menu_owner=s.menu,capture=s.capture)
                    record['shift_down' if shift else 'plain_down']=state
                    if menu or capture:return state
                return wait_for(observed,3)
            def dismiss():
                # Escape belongs only to the owned menu. Post cancel as well if the
                # menu did not already end when the left button was released.
                if desktop.state().flags&0x1c or desktop.state().menu:
                    assert u.PostMessageW(hwnd,0x1f,0,0)
                wait_for(lambda:not (desktop.state().flags&0x1c or desktop.state().menu))
            plain,_=phase('plain',CSI+'?1002;1006h'); state=press(False);desktop.event(None,False);dismiss()
            assert state['menu'] and drain(plain)==ACK*2,state
            gesture,_=phase('selection',CSI+'?1002;1006;2004h'); state=press(True)
            if state['menu']:
                desktop.event(None,False);desktop.event(0x10,False);dismiss()
                record['shift_wire']=drain(gesture).hex()
                raise AssertionError('Shift+left entered the system menu at the monitor corner')
            assert state['terminal_capture'];desktop.point(end,y)
            def highlighted():
                im=shot();diff=ImageChops.difference(before,im)
                return im if all(diff.crop((ox+n*cw,oy,ox+(n+1)*cw,y1)).getbbox() for n in range(4)) and not diff.crop((x1,oy,x1+cw,y1)).getbbox() else None
            wait_for(highlighted).save(dest/'selected.png');desktop.event(None,False);desktop.event(0x10,False)
            wait_for(lambda:desktop.state().capture!=hwnd)
            set_clipboard(hwnd,'fresh sentinel');n=u.GetClipboardSequenceNumber();desktop.chord(0x11,0x10,ord('C'))
            wait_for(lambda:u.GetClipboardSequenceNumber()!=n);record['clipboard']=clipboard_text(hwnd);assert record['clipboard']==LABEL
            desktop.chord(0x11,0x10,ord('V'));payload=b'\x1b[200~'+LABEL.encode()+b'\x1b[201~'
            wait_snapshot(lambda:read_snapshot(report),lambda v:bytes.fromhex(v.get('hex','')).endswith(payload))
            raw=drain(gesture);record['shift_wire']=raw.hex();assert raw==ACK+payload+ACK,raw
        finally:
            if desktop:desktop.restore()
            if surface:record['capture']=surface.close()
            saved.restore();write_snapshot(control,dict(stop=True));record['returncode']=proc.wait(timeout=10)
        record['cleanup']=job.finish();assert not record['cleanup']['terminated_remaining'] and record['returncode']==0


if __name__=='__main__':
    label=sys.argv[1];engine={'gdi':1,'directx':3}[label];record={}
    dest=root/'research'/('fullscreen-corner-'+label);dest.mkdir(parents=True,exist_ok=True)
    try:run(engine,dest,record);record['passed']=True
    except BaseException as exc:record['error']=repr(exc);raise
    finally:(dest/'result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
