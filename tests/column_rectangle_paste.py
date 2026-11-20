"""Drag a rectangle across a live column edit; round-trip whole Unicode glyphs."""
import argparse
import io
import json
import os

from PIL import Image
from clipboard_test_utils import SavedClipboard, clipboard_text
from hosted_gesture_input import DesktopInput
from native_test_utils import c, root, terminal_host, u, w, wait_for
from presented_window_capture import PresentedWindowCapture
from protocol_oracle_window import run

CSI = '\x1b['
ACK = b'\x1b[0n'
SUFFIX = ('中\U00020000', 'se\u0301界')  # Both are four cells, with different glyph boundaries.
COPIED = '中\U00020000\r\ne\u0301界'
MODES = (1002, 1006, 2004, 2006)
QUERY = ''.join(f'{CSI}?{m}$p' for m in MODES)
REPLY = ''.join(f'{CSI}?{m};1$y' for m in MODES).encode()


def exercise(label, renderer, out):
    def check(hwnd, phase, current):
        owner = w.DWORD()
        assert u.GetWindowThreadProcessId(hwnd, c.byref(owner))
        u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE
        assert u.GetPropW(hwnd, 'NemotermRenderer') == renderer + 1
        record = dict(renderer=label, font=os.environ['NEMOTERM_TEST_FONT'], completed=False)
        saved = SavedClipboard(hwnd)
        desk = surface = None
        try:
            desk = DesktopInput(owner.value, terminal_host(hwnd), hwnd, record.setdefault('desktop', {}))
            surface = PresentedWindowCapture(owner.value, hwnd, directx=renderer == 2, raise_window=False)
            surface.wait_for_initial_geometry()
            r = w.RECT(); assert u.GetClientRect(hwnd, c.byref(r))
            cw, dx = divmod(r.right-2, 80); ch, dy = divmod(r.bottom-2, 24)
            assert not (dx or dy) and min(cw, ch) > 0
            record['cell'] = [cw, ch]

            def aim(x, y): desk.point(1+x*cw+cw//2, 1+y*ch+ch//2)
            def tiles(im, x, y, n=1):
                return im.crop((1+x*cw, 1+y*ch, 1+(x+n)*cw, 1+(y+1)*ch)).tobytes()
            def frame(): return Image.open(io.BytesIO(surface.capture())).convert('RGB')
            def shot(name, predicate):
                last = None
                def sample():
                    nonlocal last
                    last = frame()
                    return last if predicate(last) else None
                try: return wait_for(sample)
                finally:
                    if last is not None: last.crop((1, 1, 1+27*cw, 1+10*ch)).save(out/(name+'.png'))

            # Paint the expected final rows separately, outside the scrolling region.
            # They are ordinary reference text, never copied or selected by the gesture.
            seq = CSI+'?1049h'+CSI+'?25l'+CSI+'2J'
            for n, suffix in enumerate(SUFFIX):
                seq += f'{CSI}{3+n};1HABCDEIJKLMNOPQR{suffix}   WXYZ'
                seq += f'{CSI}{8+n};1HABCDEFGHIJKLMNOPQR{suffix}WXYZ'
            phase('draw', seq+CSI+'?69h'+CSI+'5;22s'+CSI+'5;17r'+CSI+'?1002;1006;2004;2006h'+QUERY, REPLY)
            first = shot('before', lambda im: all(tiles(im,18,7+n,4)==tiles(im,15,2+n,4) and
                         tiles(im,5,7+n,3)!=tiles(im,5,2+n,3) and tiles(im,22,7+n,4)==tiles(im,22,2+n,4)
                         for n in (0,1)))
            aim(21,7)  # last cell of supplementary CJK, before it moves
            desk.event(0x10,True); desk.event(0x11,True); desk.event(None,True)
            wait_for(lambda: desk.state().capture == hwnd)
            phase('delete-columns', CSI+'8;6H'+CSI+"3'~"+QUERY, REPLY)
            after = shot('edited', lambda im: all(tiles(im,0,7+n,26)==tiles(first,0,2+n,26) for n in (0,1)))
            aim(16,8); desk.event(None,False)
            wait_for(lambda: desk.state().capture != hwnd)
            desk.event(0x11,False); desk.event(0x10,False)
            def selected(im):
                record['highlight'] = [[x for x in range(27) if tiles(im,x,7+n)!=tiles(after,x,7+n)] for n in (0,1)]
                return record['highlight'] == [[15,16,17,18], [16,17,18]]
            shot('selected', selected)
            for name, keys in [('right',('right',)), ('shortcut',(0x11,0x10,ord('C')))]:
                serial = u.GetClipboardSequenceNumber(); desk.chord(*keys)
                wait_for(lambda: u.GetClipboardSequenceNumber() != serial)
                record[name] = clipboard_text(hwnd)
                assert record[name] == COPIED, (name, repr(record[name]), repr(COPIED))
            expected = REPLY + ACK + b'\x1b[200~' + COPIED.replace('\r\n','\n').encode() + b'\x1b[201~'
            record['expected_wire'] = (expected + b'z').hex()
            desk.chord(0x11,0x10,ord('V'))
            wait_for(lambda: bytes.fromhex(current()['hex']).endswith(b'\x1b[201~'))
            desk.chord(ord('Z'))
            record['wire'] = wait_for(lambda: v if (v:=current()['hex']).endswith('7a') else None)
            assert record['wire'] == record['expected_wire'], record
            record['completed'] = True
            return record
        finally:
            try:
                if surface: surface.close()
                if desk: desk.restore()
            finally:
                saved.restore()
                (out/'gesture.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf8')
    return check


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('renderer',choices=['gdi','directx']); args = p.parse_args()
    if os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted': raise SystemExit('GitHub-hosted desktop required')
    os.environ['NEMOTERM_TEST_INPUT_CP'] = '65001'
    name = 'column-rectangle-'+args.renderer; renderer = {'gdi':0,'directx':2}[args.renderer]
    out = root/'research'/name; out.mkdir(exist_ok=True, parents=True)
    run(name, [], exercise=exercise(args.renderer,renderer,out), barrier=(CSI+'5n',ACK), font=os.environ['NEMOTERM_TEST_FONT'],
        source_reference='Independent reference rows, physical pointer, Windows clipboard and exact child input',
        profile=dict(NemoTabs=1,NemoRenderer=renderer,NemoTabSide=3,ScrollBar=0,WindowBorder=1,WarnOnClose=0,FontHeight=10))
