"""A terminal page-size request should only change a selection if its text disappears."""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import time
import traceback

from clipboard_test_utils import SavedClipboard, clipboard_text, set_clipboard
from hosted_gesture_input import DesktopInput
from native_test_utils import capture_result, root, terminal_host, u, wait_for
from presented_window_capture import PresentedWindowCapture
from protocol_oracle_window import run

CSI = '\x1b['
ACK = b'\x1b[0n'
# name, args, expected grid, initial press or completed selection, disabled, tabbed.
CASES = [
    ('lines-same', '24t', (80, 24), False, False, True),
    ('rows-same', '24*|', (80, 24), True, False, True),
    ('cols-same', '80$|', (80, 24), False, False, True),
    ('lines-grow', '28t', (80, 28), True, False, True),
    ('rows-grow', '28*|', (80, 28), False, False, True),
    ('cols-grow', '86$|', (86, 24), True, False, True),
    ('lines-denied', '28t', (80, 24), True, True, True),
    ('rows-denied', '28*|', (80, 24), False, True, True),
    ('cols-denied', '86$|', (80, 24), True, True, True),
    ('lines-standalone', '28t', (80, 28), False, False, False),
    ('rows-standalone', '28*|', (80, 28), True, False, False),
    ('cols-standalone', '86$|', (86, 24), False, False, False),
    ('cols-drop-glyph', '72$|', (72, 24), True, False, True),
    ('xtwinops-control', '8;27;84t', (84, 27), False, False, True),
]


def exercise_case(gpu, case):
    tag, op, want_grid, held, denied, tabs = case
    renderer = {'gdi': 1, 'directx': 3}[gpu]
    name = f'column-mode-page-{gpu}-{tag}'
    font = os.environ['NEMOTERM_TEST_FONT']
    sha = hashlib.sha256(Path(os.environ['NEMOTERM_TEST_EXE']).read_bytes()).hexdigest()
    keep = tag != 'cols-drop-glyph'
    rec = dict(name=tag, executable_sha256=sha, requested_font=font, command=op,
               held=held, denied=denied, tabbed=tabs, expected_grid=want_grid,
               expected_text='A中Z' if keep else None, passed=False)

    def exercise(hwnd, phase, current):
        host = terminal_host(hwnd)
        assert (host != hwnd) == tabs
        u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE
        rec['renderer'] = int(u.GetPropW(hwnd, 'NemotermRenderer') or 0)
        assert rec['renderer'] == renderer
        def size(target):
            r = w.RECT(); assert u.GetClientRect(target, c.byref(r)); return (r.right, r.bottom)
        cw, ch = rec['cell'] = ((size(hwnd)[0]-2)//80, (size(hwnd)[1]-2)//24)
        pid = w.DWORD(); u.GetWindowThreadProcessId(hwnd, c.byref(pid))
        clip = SavedClipboard(hwnd); desk = camera = None
        y = 3; left = 2 if keep else 75; end = left+3 if keep else 8
        marker = bytes((85, 51, 34))
        def observe_frame():
            width, height = size(hwnd)
            if (width, height) != size(camera.surface): return None
            pixels = camera.capture()[54:]
            def selected(x):
                offset = 4*((2+y*ch)*width + 2+x*cw)
                return pixels[offset:offset+3] == marker
            return (width, height), pixels, [x for x in range((width-2)//cw) if selected(x)]
        def frame(label, expected=None):
            # The DSR confirms parsing, not that the resulting paint has been presented.
            last = None; stable = time.monotonic(); deadline = stable+2
            while time.monotonic() < deadline:
                result = observe_frame()
                if result:
                    geom, _, marks = result
                    value = (geom, marks)
                    if value != last: stable = time.monotonic(); last = value
                    elif time.monotonic()-stable >= .16 and (expected is None or marks == expected): break
                time.sleep(.03)
            assert result, label
            geom, pixels, marks = result
            capture_result(*geom, pixels, f'{name}-{label}.png'); rec[label] = marks
            if expected is not None: assert marks == expected, (label, marks, expected)
        try:
            desk = DesktopInput(pid.value, host, hwnd, rec.setdefault('input', {}))
            camera = PresentedWindowCapture(pid.value, hwnd, directx=renderer==3); camera.wait_for_initial_geometry()
            def aim(x): desk.point(1+x*cw+cw//2, 1+y*ch+ch//2)
            scene = CSI+'?1049h'+CSI+'?25l'+CSI+'?1002;1006h'+'\x1b]17;#223355\x07'+f'{CSI}{y+1};{left}H|A中Z|'+CSI+'1;1H'
            phase('draw',scene+CSI+'?1002$p'+CSI+'?1006$p', b'\x1b[?1002;1$y\x1b[?1006;1$y'); frame('drawn',[])
            set_clipboard(hwnd, 'page resize sentinel'); aim(left); desk.event(0x10,True)
            if held: desk.event(0x11,True)
            desk.event(None,True); wait_for(lambda: desk.state().capture==hwnd)
            if not held:
                aim(end); desk.event(None,False); desk.event(0x10,False); wait_for(lambda: desk.state().capture != hwnd)
                frame('selected',list(range(left,end+1)))
            phase('resize', CSI+op, b'')
            until = time.monotonic()+2
            while time.monotonic()<until:
                q=current(); grid=(q['columns'],q['rows']); geom=size(hwnd)
                if grid==want_grid and geom==(want_grid[0]*cw+2,want_grid[1]*ch+2): break
                time.sleep(.04)
            rec['child_grid']=grid;rec['client_pixels']=geom
            rec['vt_grid_wire']=phase('measure',CSI+'18t',None).hex()
            if held:
                desk.event(0x11,False);desk.event(0x10,False);aim(end);desk.event(None,False)
                wait_for(lambda:desk.state().capture!=hwnd)
            desk.chord(ord('7'));raw=wait_for(lambda:b if (b:=bytes.fromhex(current()['hex'])).endswith(b'7') else None)
            rec['gesture_wire']=raw.hex();frame('after')
            phase('copy','',b'');previous=u.GetClipboardSequenceNumber()
            if keep: desk.chord(0x11,0x10,ord('C'))
            desk.chord(ord('8'));rec['copy_wire']=wait_for(lambda:b if (b:=bytes.fromhex(current()['hex'])).endswith(b'8') else None).hex()
            rec['shortcut_copy']=clipboard_text(hwnd) if u.GetClipboardSequenceNumber()!=previous else None
            phase('right','',b'');previous=u.GetClipboardSequenceNumber();aim(end);desk.chord('right');desk.chord(ord('9'))
            rec['right_wire']=wait_for(lambda:b if (b:=bytes.fromhex(current()['hex'])).endswith(b'9') else None).hex()
            rec['right_copy']=clipboard_text(hwnd) if u.GetClipboardSequenceNumber()!=previous else None
            position = f'{CSI}8;{want_grid[1]};{want_grid[0]}t'.encode()
            pointer = b'' if keep else f'{CSI}<2;{end+1};{y+1}M{CSI}<2;{end+1};{y+1}m'.encode()
            rec['checks']=dict(geometry=grid==want_grid and geom==(want_grid[0]*cw+2,want_grid[1]*ch+2),
                terminal=rec['vt_grid_wire']==position.hex(), ownership=raw==position+ACK+b'7',
                highlight=rec['after']==(list(range(left,end+1)) if keep else []),
                clipboard=rec['shortcut_copy']==rec['right_copy']==rec['expected_text'],
                copy_key=rec['copy_wire']==(ACK+b'8').hex(), right_button=rec['right_wire']==(ACK+pointer+b'9').hex())
        finally:
            if camera:camera.close()
            if desk:desk.restore()
            clip.restore()
    try:
        run(name, [], exercise=exercise, barrier=(CSI+'5n',ACK), font=font, source_reference='Window/Win32 grid and selected text',
            profile=dict(NemoTabs=int(tabs),NemoRenderer=renderer-1,FontHeight=8,WarnOnClose=0,NoRemoteResize=int(denied),LockSize=0,MouseOverride=1))
        rec['passed']=all(rec['checks'].values())
    except Exception: rec['error']=traceback.format_exc()
    (root/'research'/f'{name}-result.json').write_text(json.dumps(rec,indent=2),encoding='utf-8');return rec['passed']


if __name__=='__main__':
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise RuntimeError('Requires a hosted desktop')
    results = [exercise_case(os.environ['RENDERER'],case) for case in CASES]
    raise SystemExit(not all(results))
