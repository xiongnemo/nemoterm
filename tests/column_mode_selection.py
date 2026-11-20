"""Shift-select a wide glyph while an application owns the mouse, then change columns."""
import ctypes as c
import json
import os
import struct
from ctypes import wintypes as w

from clipboard_test_utils import SavedClipboard, clipboard_text, set_clipboard
from hosted_gesture_input import DesktopInput
from native_test_utils import capture_result, root, terminal_host, u, wait_for
from presented_window_capture import PresentedWindowCapture
from protocol_oracle_window import run

CSI = '\x1b['
ACK = b'\x1b[0n'


def observe(case, gpu):
    renderer = {'gdi': 1, 'directx': 3}[gpu]
    name = f'column-mode-selection-{gpu}-{case}'
    record = dict(case=case, renderer=renderer, frames={}, passed=False)

    def exercise(hwnd, phase, current):
        u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE
        assert u.GetPropW(hwnd, 'NemotermRenderer') == renderer
        rect = w.RECT(); assert u.GetClientRect(hwnd, c.byref(rect))
        cw, ch = (rect.right-2)//80, (rect.bottom-2)//24
        pid = w.DWORD(); u.GetWindowThreadProcessId(hwnd,c.byref(pid))
        clip = SavedClipboard(hwnd); desk = camera = None
        def frame(label, cols, expected):
            def sample():
                for target in (hwnd, camera.surface):
                    rect = w.RECT(); assert u.GetClientRect(target,c.byref(rect))
                    if (rect.right,rect.bottom) != (2+cw*cols,2+ch*24): return None
                bmp = camera.capture(); width,height = struct.unpack_from('<ii',bmp,18)
                marks = []
                for x in range(1,7):
                    at = 54 + 4*((2+ch)*width+2+x*cw)
                    if bmp[at:at+3] == bytes.fromhex('553322'): marks.append(x)
                record['frames'][label] = dict(size=[width,-height],selected=marks,expected=expected)
                return bmp if marks==expected else None
            picture = wait_for(sample,timeout=4)
            capture_result(2+cw*cols,2+ch*24,picture[54:],name+'-'+label+'.png')
        try:
            desk = DesktopInput(pid.value,terminal_host(hwnd),hwnd,record.setdefault('input',{}))
            camera = PresentedWindowCapture(pid.value,hwnd,directx=renderer==3);camera.wait_for_initial_geometry()
            set_clipboard(hwnd,'column selection sentinel')
            draw = CSI+'?25l'+CSI+'?1002;1006h'+'\x1b]17;#223355\x07'+CSI+'2;2H|A中Z|'+CSI+'7;11H'
            phase('draw',draw+CSI+'?1002$p'+CSI+'?1006$p',b'\x1b[?1002;1$y\x1b[?1006;1$y')
            frame('before',80,[])
            phase('gesture','','')
            def point(x): return desk.point(1+x*cw+cw//2,1+ch+ch//2)
            point(2);desk.event(0x10,True);desk.event(None,True)
            wait_for(lambda:desk.state().capture==hwnd);point(5)
            frame('held',80,[2,3,4,5]);desk.event(None,False);desk.event(0x10,False)
            wait_for(lambda:desk.state().capture!=hwnd)
            desk.chord(ord('7'));wait_for(lambda:bytes.fromhex(current()['hex']).endswith(b'7'))
            record['gesture_wire']=current()['hex'];assert bytes.fromhex(record['gesture_wire'])==ACK+b'7'
            permit='l' if case=='ignored' else 'h'; keep='l' if case=='clear' else 'h'
            cols=80 if case=='ignored' else 132
            phase('switch',CSI+'?40'+permit+CSI+'?95'+keep+CSI+'?3h'+CSI+'18t',f'\x1b[8;24;{cols}t')
            frame('after',cols,[] if case=='clear' else [2,3,4,5])
            if case!='clear':
                previous=u.GetClipboardSequenceNumber();desk.chord(0x11,0x10,ord('C'))
                wait_for(lambda:u.GetClipboardSequenceNumber()!=previous)
                record['clipboard']=clipboard_text(hwnd);assert record['clipboard']=='A中Z'
                desk.chord(ord('7'));wait_for(lambda:bytes.fromhex(current()['hex']).endswith(b'7'))
                record['copy_wire']=current()['hex'];assert bytes.fromhex(record['copy_wire'])==f'\x1b[8;24;{cols}t'.encode()+ACK+b'7'
        finally:
            if camera:camera.close()
            if desk:desk.restore()
            clip.restore()
    try:
        run(name,[],exercise=exercise,barrier=(CSI+'5n',ACK),font=os.environ['NEMOTERM_TEST_FONT'],
            profile=dict(NemoTabs=1,NemoRenderer=renderer-1,FontHeight=8,WarnOnClose=0,NoRemoteResize=0,LockSize=0,MouseOverride=1))
        record['passed']=True
    finally:
        (root/'research'/(name+'-result.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    if os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise RuntimeError('Requires a hosted desktop')
    failures=[]
    for case in ('keep','ignored','clear'):
        try: observe(case,os.environ['RENDERER'])
        except Exception as error: failures.append((case,repr(error)))
    assert not failures,failures
