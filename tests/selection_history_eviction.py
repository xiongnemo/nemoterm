"""Check what remains highlighted as a full scrollback buffer evicts selected rows."""
import ctypes as c
from ctypes import wintypes as w
import json
import os
import struct

from clipboard_test_utils import SavedClipboard, clipboard_text
from hosted_gesture_input import DesktopInput
from native_test_utils import capture_result, root, terminal_host, u, wait_for
from presented_window_capture import PresentedWindowCapture
from protocol_oracle_window import run
from selection_history_drag import ScrollInfo

CSI = '\x1b['
INK = bytes.fromhex('553322')  # BGR for selection background #223355


def line(i):
    # The two blank coloured cells are outside the selection and identify the row.
    return f'ROW|{i:02}中!|GUARD{CSI}48;2;{40+i};90;130m  {CSI}0m'


def exercise(hwnd, phase, current):
    pid = w.DWORD(); u.GetWindowThreadProcessId(hwnd, c.byref(pid))
    renderer = {'gdi': 1, 'directx': 3}[os.environ['RENDERER']]
    u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE
    assert int(u.GetPropW(hwnd, 'NemotermRenderer') or 0) == renderer
    u.GetScrollInfo.argtypes = [w.HWND, c.c_int, c.POINTER(ScrollInfo)]
    def position():
        s = ScrollInfo(); s.size = c.sizeof(s); s.mask = 7
        assert u.GetScrollInfo(hwnd, 1, c.byref(s)); return [s.pos, s.high-int(s.page)+1]
    r = w.RECT(); assert u.GetClientRect(hwnd, c.byref(r))
    cw, ch = (r.right-2)//80, (r.bottom-2)//24
    observed = dict(renderer=renderer, frames={}, input={})
    clip = SavedClipboard(hwnd); desk = camera = None
    def frame(name, first, rows, *, wait_for_shape=False):
        expected = [list(range(4, 9)) if y < rows else [] for y in range(5)]
        def sample():
            bmp = camera.capture(); width, height = struct.unpack_from('<ii',bmp,18)
            assert (width, -height) == (r.right, r.bottom)
            def colour(x, y):
                offset = 54+4*((2+y*ch)*width+2+x*cw)
                return bmp[offset:offset+3]
            labels = [colour(15,y).hex() for y in range(5)]
            want = [bytes([130,90,40+first+y]).hex() for y in range(5)]
            painted = [[x for x in range(12) if colour(x,y) == INK] for y in range(5)]
            observed['frames'][name] = dict(row_markers=labels,expected_markers=want,selected=painted,expected=expected,position=position())
            if labels == want and (not wait_for_shape or painted == expected): return bmp
        try:
            picture = wait_for(sample, timeout=5)
        except Exception:
            picture = camera.capture(); capture_result(r.right,r.bottom,picture[54:],f'scrollback-rectangle-{name}-unmatched.png'); raise
        capture_result(r.right,r.bottom,picture[54:],f'scrollback-rectangle-{name}.png')
    def point(x,y): return desk.point(1+x*cw+cw//2, 1+y*ch+ch//2)
    try:
        desk = DesktopInput(pid.value,terminal_host(hwnd),hwnd,observed['input'])
        camera = PresentedWindowCapture(pid.value,hwnd,directx=renderer==3); camera.wait_for_initial_geometry()
        phase('fill',CSI+'?25l'+CSI+'?1010l'+CSI+'?1002;1006h'+'\x1b]17;#223355\x07'+'\r\n'.join(line(i) for i in range(56)),'')
        wait_for(lambda:position()[1]==32); u.SendMessageW(hwnd,0x115,6,0); wait_for(lambda:position()==[0,32])
        frame('unselected',0,0,wait_for_shape=True)
        point(4,0); desk.event(0x11,True); desk.event(0x10,True); desk.event(None,True)
        wait_for(lambda:desk.state().capture==hwnd); point(8,2)
        frame('held',0,3,wait_for_shape=True)
        desk.event(None,False); wait_for(lambda:desk.state().capture!=hwnd); desk.event(0x10,False); desk.event(0x11,False)
        seq = u.GetClipboardSequenceNumber(); desk.chord(0x11,0x10,ord('C')); wait_for(lambda:u.GetClipboardSequenceNumber()!=seq)
        observed['copy'] = clipboard_text(hwnd); assert observed['copy']=='00中!\r\n01中!\r\n02中!'
        observed['wire_before_output']=current()['hex']; assert observed['wire_before_output']=='1b5b306e'
        frame('released',0,3,wait_for_shape=True)
        for n in range(1,5):
            phase('evict-'+str(n),'\r\n'+line(55+n),''); frame('evicted-'+str(n),n,max(0,3-n))
        observed['clipboard_after']=clipboard_text(hwnd)
    finally:
        try:
            if camera: observed['capture']=camera.close()
            if desk: desk.restore()
        finally:
            clip.restore(); (root/'research/scrollback-rectangle.json').write_text(json.dumps(observed,indent=2))
    return observed


if __name__=='__main__':
    assert os.environ['RUNNER_ENVIRONMENT']=='github-hosted'
    run('scrollback-modes-rectangle',[],exercise=exercise,barrier=(CSI+'5n',b'\x1b[0n'),source_reference='Native Windows selection',
        font=os.environ['NEMOTERM_TEST_FONT'],profile=dict(ScrollbackLines=32,ScrollBar=1,WarnOnClose=0,NemoRenderer={'gdi':0,'directx':2}[os.environ['RENDERER']]))
    record=json.loads((root/'research/scrollback-rectangle.json').read_bytes())
    assert record['clipboard_after']==record['copy']
    assert all(f['selected']==f['expected'] and f['position']==[0,32] for f in record['frames'].values()),record['frames']
