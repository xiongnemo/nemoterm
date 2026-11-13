"""DECALN state, full-grid pixels, Sixel lifetime and synchronized output."""
import argparse
from alignment_oracle_cases import CASES
from protocol_oracle_window import run
from native_test_utils import capture, hashlib, terminal_host, u, c, w, wait_for, time, os
from gpu_capture import OwnedGPUCapture

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--renderer', choices=('gdi', 'directx', 'opengl'), default='gdi')
args = parser.parse_args()
requested = {'gdi': 0, 'opengl': 1, 'directx': 2}[args.renderer]
name = 'alignment-'+args.renderer
ESC, CSI, DCS, ST = '\x1b', '\x1b[', '\x1bP', '\x1b\\'
RESET = CSI+'65;1"p'+ESC+'c'+CSI+'?25l'
IMAGE = CSI+'4;4H'+DCS+'0;1q"1;1;48;18#1;2;100;0;0'+3*'!48~-'+ST
SCENE = RESET+CSI+'1;3;4:3;31;44m'+CSI+'2;3H中文 e\u0301'+ESC+'#6'+CSI+'0m'
u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE
RGB = ('rgb-retains-valid-colour-encoding', RESET+CSI+'38:2::1:2:3;48:2::4:5:6m'+ESC+'#8'+DCS+'$qm'+ST,
       DCS+'1$r0;38:2::1:2:3;48:2::4:5:6m'+ST)


def exercise(hwnd, phase, current):
    pid = w.DWORD(); u.GetWindowThreadProcessId(hwnd, c.byref(pid))
    actual = int(u.GetPropW(hwnd, 'NemotermRenderer') or 0)
    assert actual in (1, 2, 3), actual
    if requested == 0: assert actual == 1
    if requested == 1 and os.environ.get('NEMOTERM_REQUIRE_OPENGL') == '1': assert actual == 2
    if requested == 2 and os.environ.get('NEMOTERM_REQUIRE_DIRECTX') == '1': assert actual == 3
    evidence = dict(actual_renderer=actual, pixel_checks=[], memory_instrumented=actual != 1,
                    clipboard_access=False, global_input=False)
    gpu = OwnedGPUCapture(pid.value, hwnd) if actual != 1 else None
    try:
        def pixels():
            return gpu.capture(return_pixels=True) if gpu else capture(hwnd, return_pixels=True)
        def draw(label, sequence, expected=None):
            phase(label, sequence, '')
            if expected is not None: wait_for(lambda: pixels() == expected)
            else: time.sleep(.1)
            data = pixels()
            if expected is not None: assert data == expected, label
            evidence['pixel_checks'].append(dict(name=label, sha256=hashlib.sha256(data).hexdigest()))
            return data
        def reference():
            columns, rows = current()['columns'], current()['rows']
            return RESET+CSI+'?7l'+''.join(CSI+f'{row+1};1H'+'E'*columns for row in range(rows))

        expected = draw('explicit-full-E-grid', reference())
        text = draw('styled-wide-and-combining-before', SCENE)
        picture = draw('visible-sixel-before', IMAGE)
        assert picture != text and text != expected
        draw('alignment-retires-text-and-sixel', ESC+'#8', expected)
        assert current()['columns'] == 80 and current()['rows'] == 24

        original = draw('main-screen-image', SCENE+IMAGE)
        draw('alternate-aligned', CSI+'?47h'+ESC+'#8', expected)
        draw('main-screen-image-retained', CSI+'?47l', original)
        draw('synchronized-alignment-held', CSI+'?2026h'+ESC+'#8', original)
        draw('synchronized-alignment-released', CSI+'?2026l', expected)

        before = [current()['columns'], current()['rows']]
        assert u.MoveWindow(terminal_host(hwnd), 50, 50, 780, 540, True)
        phase('resized-geometry', CSI+'18t', None)
        resized = [current()['columns'], current()['rows']]
        assert resized != before and min(resized) > 0, resized
        expected = draw('resized-explicit-full-grid', reference())
        draw('resized-image', SCENE+IMAGE)
        draw('resized-alignment', ESC+'#8', expected)
        evidence['resized_grid'] = resized
        if gpu: gpu.capture(name+'-window.png')
        else: capture(hwnd, name+'-window.png')
        return evidence
    finally:
        if gpu: gpu.close()


run(name, CASES, extra_cases=(RGB,), exercise=exercise,
    profile=dict(NemoRenderer=requested, MouseAutocopy=0, WarnOnClose=0),
    font=os.environ.get('NEMOTERM_TEST_FONT',
        'Consolas' if os.environ.get('CI') == 'true' else 'SarasaTermSC Nerd Font Light'))
