"""A real local Shift drag across text moving on top of a retained ReGIS line."""
import ctypes as c
from ctypes import wintypes as w
import json
import os
import time
import traceback

from clipboard_test_utils import SavedClipboard, clipboard_text, set_clipboard
from hosted_gesture_input import DesktopInput
from native_test_utils import root, u, wait_for, terminal_host, capture_result
from presented_window_capture import PresentedWindowCapture
from protocol_oracle_window import run

CSI = '\x1b['
ACK = b'\x1b[0n'


def replay(renderer, op, delta, rectangle):
    name = 'regis-selection-' + renderer + '-' + op
    font = os.environ['NEMOTERM_TEST_FONT']
    row = 3
    left = 7  # A, both cells of 中, Z
    first, last = (left+3, left) if rectangle else (left, left+3)
    record = dict(operation=op, rectangle=rectangle, renderer=renderer, font=font)

    def exercise(hwnd, phase, current):
        pid = w.DWORD(); u.GetWindowThreadProcessId(hwnd, c.byref(pid))
        host = terminal_host(hwnd); assert host != hwnd
        u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE
        assert int(u.GetPropW(hwnd,'NemotermRenderer') or 0) == {'gdi':1, 'directx':3}[renderer]
        rect = w.RECT(); assert u.GetClientRect(hwnd, c.byref(rect))
        width, height = rect.right, rect.bottom
        cw, ch = (width-2)//80, (height-2)//24
        assert (cw*80+2, ch*24+2) == (width,height)
        y = (row+1)*ch-2
        x1, x2 = 2*cw, 17*cw
        def point(x): desk.point(1+x*cw+cw//2, 1+row*ch+ch//2)
        def snapshot(label, predicate):
            deadline = time.monotonic()+3; previous = None; since = time.monotonic()
            while True:
                bmp = camera.capture(); pixels = bmp[54:]
                def rgb(x,py):
                    i=4*((py+1)*width+x+1); return pixels[i:i+3]
                ink = [x for x in range(x1,x2+1) if rgb(x,y)==b'\x00\x00\xff']
                marked = [x for x in range(20) if rgb(1+x*cw,1+row*ch)==bytes((85,51,34))]
                def glyphs(x):
                    return b''.join(rgb(col,py) for py in range(row*ch,y) for col in range(x*cw,(x+4)*cw))
                state=(ink,marked,glyphs(left),glyphs(left+delta))
                now=time.monotonic()
                if state!=previous: previous=state;since=now
                if (now-since>=.12 and predicate(*state)) or now>=deadline:break
                time.sleep(.025)
            record[label]=dict(ink=ink,highlight=marked,matched=predicate(*state))
            capture_result(width,height,pixels,name+'-'+label+'.png')
            return state
        def fence(key):
            desk.chord(ord(key));return wait_for(lambda:b if (b:=bytes.fromhex(current()['hex'])).endswith(key.encode()) else None)
        expected=[x for x in range(x1,x2+1) if x<4*cw or x>=13*cw]; clip=SavedClipboard(hwnd);desk=camera=None
        try:
            desk=DesktopInput(pid.value,host,hwnd,record.setdefault('input',{}))
            camera=PresentedWindowCapture(pid.value,hwnd,directx=renderer=='directx');camera.wait_for_initial_geometry()
            scene=(CSI+'?25l'+CSI+'?1002;1006h'+'\x1b]17;#223355\x07'+
                   f'\x1bP1pS(E)S(M2(R100G0B0))W(I2)P[{x1},{y}]V[{x2},{y}]\x1b\\'+
                   f'{CSI}{row+1};5H'+CSI+'9X'+f'{CSI}{row+1};{left+1}HA中Z'+CSI+'?69h'+CSI+'3;18s'+CSI+'3;6r')
            phase('seed',scene+CSI+'?1002$p'+CSI+'?1006$p',b'\x1b[?1002;1$y\x1b[?1006;1$y')
            glyph=snapshot('seed', lambda ink,marks,a,b: ink==expected and marks==[] and max(a)>128)[2]
            assert record['seed']['matched']
            set_clipboard(hwnd,'regis selection sentinel');point(first);desk.event(0x10,True)
            if rectangle:desk.event(0x11,True)
            desk.event(None,True);wait_for(lambda:desk.state().capture==hwnd)
            phase('edit',f'{CSI}{row+1};5H'+CSI+('2@' if op=='ich' else '2 @'),b'')
            snapshot('edited',lambda ink,marks,a,b: ink==expected and marks==[] and b==glyph)
            if rectangle:desk.event(0x11,False)
            desk.event(0x10,False);point(last+delta);desk.event(None,False);wait_for(lambda:desk.state().capture!=hwnd)
            record['gesture_wire']=fence('7').hex();selected=list(range(left+delta,left+delta+4))
            snapshot('selected',lambda ink,marks,a,b:marks==selected)
            for label,keys,key in [('shortcut',(0x11,0x10,ord('C')),'8'),('right',('right',),'9')]:
                phase(label,'',b'');n=u.GetClipboardSequenceNumber();desk.chord(*keys);wire=fence(key)
                record[label]=dict(text=clipboard_text(hwnd) if u.GetClipboardSequenceNumber()!=n else None,wire=wire.hex(),
                                   expected_wire=(ACK+key.encode()).hex())
            record['passed']=(all(record[k]['matched'] for k in ('seed','edited','selected')) and record['gesture_wire']==(ACK+b'7').hex() and
                              all(record[k]['text']=='A中Z' and record[k]['wire']==record[k]['expected_wire'] for k in ('shortcut','right')))
        finally:
            try:
                if desk:desk.restore()
                if camera:camera.close()
            finally:clip.restore()
    try:
        run(name,[],exercise=exercise,barrier=(CSI+'5n',ACK),font=font,source_reference='Windows presented text and ReGIS lines during physical input',
            profile=dict(NemoTabs=1,NemoRenderer={'gdi':0,'directx':2}[renderer],FontHeight=8,WarnOnClose=0,MouseOverride=1,MouseAutocopy=0))
    except Exception:record['error']=traceback.format_exc()
    (root/'research'/(name+'-result.json')).write_text(json.dumps(record,indent=2),encoding='utf-8')
    return record.get('passed',False) and 'error' not in record


if __name__=='__main__':
    if os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise SystemExit('Requires a GitHub hosted Windows desktop')
    outcomes=[replay(os.environ['RENDERER'],op,delta,rect) for op,delta,rect in [('ich',2,False),('sl',-2,True)]]
    raise SystemExit(not all(outcomes))
