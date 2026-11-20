"""Physical Shift selects after intervening right-copy vs an uninterrupted double click."""
import json
import os
import time
from clipboard_test_utils import SavedClipboard, clipboard_text
from hosted_gesture_input import DesktopInput
from native_test_utils import c, w, u, root, terminal_host, wait_for
from protocol_oracle_window import run

out = root/'research'/'tab-hover-native'/'right-click-chain'
out.mkdir(parents=True, exist_ok=True)
ack = b'\x1b[0n'
mode = b'\x1b[?47;2$y'
rows = []


def exercise(hwnd, phase, current):
    host = terminal_host(hwnd); assert host != hwnd
    u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
    assert u.GetPropW(hwnd,'NemotermRenderer') == 3, 'Expected a live DirectX renderer'
    owner = w.DWORD(); assert u.GetWindowThreadProcessId(hwnd, c.byref(owner))
    desk = DesktopInput(owner.value, host, hwnd, {})
    saved = SavedClipboard(hwnd)
    try:
        r = w.RECT(); assert u.GetClientRect(hwnd, c.byref(r))
        cell, dw = divmod(r.right-2, 80); line, dh = divmod(r.bottom-2, 24)
        assert not (dw or dh) and min(cell, line) > 0
        threshold = u.GetDoubleClickTime()
        for y, intervening in ((5, False), (11, True)):
            name = 'right-copy' if intervening else 'double-click'
            row = dict(case=name, double_click_ms=threshold); rows.append(row)
            def aim(x): desk.point(1+x*cell+cell//2, 1+y*line+line//2)
            def left(down):
                desk.event(None, down)
                wait_for(lambda: (desk.state().capture == hwnd) == down)
            phase(name+'-start', '\x1bc\x1b[?25l\x1b[?1002;1006h'+f'\x1b[{y+1};1H|ABCDE|', b'')
            aim(2); desk.event(0x10,True)
            start=time.monotonic_ns(); left(True)
            if intervening: aim(3)
            left(False); desk.event(0x10,False)
            if intervening:
                before=u.GetClipboardSequenceNumber()
                desk.event('right',True); desk.event('right',False)
                wait_for(lambda: u.GetClipboardSequenceNumber()!=before)
                row['right_copy']=clipboard_text(hwnd); assert row['right_copy']=='BC', row
            aim(2); desk.event(0x10,True); left(True)
            row['left_down_interval_upper_ms']=(time.monotonic_ns()-start)/1e6
            assert row['left_down_interval_upper_ms']<threshold, 'Gesture did not fit system double-click interval: '+str(row)
            def while_held(written):
                end=time.monotonic()+1.2
                reply=written
                while not bytes.fromhex(reply['hex']).endswith(ack) and time.monotonic()<end:
                    time.sleep(.015); reply=current()
                assert reply['phase']==name+'-held' and desk.state().capture==hwnd
                row['wire_while_held']=reply['hex']
                aim(3); left(False); desk.event(0x10,False)
            phase(name+'-held','\x1b[?47$p',mode,after_write=while_held)
            seq=u.GetClipboardSequenceNumber(); desk.chord(0x11,0x10,ord('C'))
            wait_for(lambda: u.GetClipboardSequenceNumber()!=seq)
            row['second_copy']=clipboard_text(hwnd)
            row['passed']=(row['second_copy']==('BC' if intervening else 'ABCDE') and
                           row['wire_while_held']==((mode+ack).hex() if intervening else ''))
        assert all(row['passed'] for row in rows), rows
        return rows
    finally:
        try: desk.restore()
        finally:
            saved.restore()
            (out/'gestures.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')


if __name__=='__main__':
    run('tab-right-click-chain', [], exercise=exercise, barrier=('\x1b[5n',ack),
        source_reference='Windows physical click sequence and console child reply',
        profile={'NemoTabs':1,'NemoRenderer':2,'NemoTabSide':3,'RightClickCopyAndPaste':0,
                 'WindowBorder':1,'ScrollBar':0,'FontHeight':10,'WarnOnClose':0},
        font=os.environ['NEMOTERM_TEST_FONT'])
