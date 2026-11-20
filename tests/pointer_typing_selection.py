"""Verify local copy starting at a hidden pointer while the child owns mouse tracking."""
import os
import sys
import json
import struct
import time
from native_test_utils import c, w, u, root, wait_for, capture_result
from clipboard_test_utils import SavedClipboard, clipboard_text, set_clipboard
from hosted_gesture_input import DesktopInput
from pointer_hiding_window import CursorInfo, observe
from presented_window_capture import PresentedWindowCapture
from protocol_oracle_window import run
from native_test_utils import terminal_host

CSI = '\x1b['
ACK = b'\x1b[0n'
REPLIES = b'\x1b[?1002;1$y\x1b[?1006;1$y'
TEXT = '|中文|'


def check(hwnd, phase, current, rec, tag, engine):
    owner = w.DWORD()
    assert u.GetWindowThreadProcessId(hwnd, c.byref(owner)) and owner.value
    rec['renderer'] = int(u.GetPropW(hwnd, 'NemotermRenderer') or 0)
    assert rec['renderer'] == engine, rec
    rect = w.RECT(); assert u.GetClientRect(hwnd, c.byref(rect))
    width, height = rect.right, rect.bottom
    cw, dx = divmod(width - 2, 80); ch, dy = divmod(height - 2, 24)
    assert not (dx or dy) and min(cw,ch)>0, (width,height,cw,ch,dx,dy)
    rec['grid'] = [width,height,cw,ch]
    input_ = DesktopInput(owner.value, terminal_host(hwnd), hwnd, rec.setdefault('desktop', {}))
    capture = clipboard = None
    try:
        capture = PresentedWindowCapture(owner.value, hwnd, engine == 3, raise_window=False)
        capture.wait_for_initial_geometry(); clipboard = SavedClipboard(hwnd)
        def sample():
            bmp = capture.capture(); assert struct.unpack_from('<ii',bmp,18) == (width,-height)
            return bmp[54:]
        def tile(frame, col, row):
            return b''.join(frame[(width*y+1+col*cw)*4:(width*y+1+(col+1)*cw)*4]
                            for y in range(1+row*ch,1+(row+1)*ch))
        def image_ready():
            image = sample()
            if all(tile(image,x,4)==tile(image,x,8) for x in range(2,8)) and all(
                len(set(tile(image,x,4)[::4]))>1 for x in (3,5)):
                return image
        mode = '?1002;1006h'
        scene = CSI+'?25l'+CSI+'2J'+CSI+'5;3H'+TEXT+CSI+'9;3H'+TEXT+CSI+'>2p'+CSI+mode
        phase(tag, scene+CSI+'?1002$p'+CSI+'?1006$p', REPLIES)
        baseline = wait_for(image_ready)
        capture_result(width,height,baseline,tag+'-before.png')
        set_clipboard(hwnd, 'before:'+tag)
        y = 1+4*ch+ch//2
        input_.point(1+3*cw+cw//2, y); input_.chord(ord('A'))
        def bytes_after(last):
            s = current()
            return s['hex'] if s.get('phase')==tag and s['hex'].endswith(last.hex()) else None
        rec['after_a'] = wait_for(lambda:bytes_after(b'a'))
        def cursor_samples():
            readings = []
            for delay in (.02,.03,.04):
                time.sleep(delay); readings.append(observe())
            return readings
        rec['typing_pointer'] = cursor_samples()
        input_.event(0x10,True); input_.event(None,True)
        wait_for(lambda:input_.state().capture==hwnd)
        input_.point(1+6*cw+cw//2, y)
        def highlighted():
            frame = sample()
            cols = [x for x in range(2,8) if tile(frame,x,4) != tile(baseline,x,4)]
            return frame if cols==[3,4,5,6] else None
        frame = wait_for(highlighted)
        capture_result(width,height,frame,tag+'-held.png'); rec['selected_columns_zero_based'] = [3,4,5,6]
        rec['drag_pointer'] = cursor_samples()
        input_.event(None,False); wait_for(lambda:not input_.state().capture); input_.event(0x10,False)
        seq = u.GetClipboardSequenceNumber(); input_.chord(0x11,0x10,ord('C'))
        wait_for(lambda:u.GetClipboardSequenceNumber()!=seq); rec['copied']=clipboard_text(hwnd)
        input_.chord(ord('B')); rec['through_b'] = wait_for(lambda:bytes_after(b'b'))
        rec['passed'] = (rec['after_a']==(REPLIES+ACK+b'a').hex() and rec['through_b']==(REPLIES+ACK+b'ab').hex()
                         and not any(r['visible'] for r in rec['typing_pointer'])
                         and all(r['visible'] for r in rec['drag_pointer']) and rec['copied']=='中文')
        return {'passed':rec['passed']}
    finally:
        input_.restore()
        if clipboard: clipboard.restore()
        if capture: rec['capture']=capture.close()


if __name__=='__main__':
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
    u.GetCursorInfo.argtypes=[c.POINTER(CursorInfo)]
    engine={'gdi':1,'directx':3}[sys.argv[1]]; tag='pointer-hiding-copy-'+sys.argv[1]
    rec={}; font=os.environ['NEMOTERM_TEST_FONT']
    try:
        run(tag,[],exercise=lambda h,p,s:check(h,p,s,rec,tag,engine),barrier=(CSI+'5n',ACK),
            profile=dict(NemoRenderer=engine-1,NemoTabs=1,HideMousePtr=0,ScrollBar=0,WindowBorder=1,
                         WarnOnClose=0,CloseOnExit=1),font=font,source_reference='physical local selection')
        assert rec['passed'], rec
    except Exception as e:
        rec['error']=repr(e); raise
    finally:
        (root/'research'/(tag+'-gesture.json')).write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf8')
