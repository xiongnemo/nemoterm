"""Position-relative movement, origin clipping and double-width write bounds."""
import argparse
from relative_cursor_oracle_cases import CASES
from protocol_oracle_window import run
from native_test_utils import capture, hashlib, terminal_host, u, c, w, wait_for, time, os
from gpu_capture import OwnedGPUCapture

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--renderer', choices=('gdi', 'opengl', 'directx'), default='gdi')
args = parser.parse_args()
requested = {'gdi': 0, 'opengl': 1, 'directx': 2}[args.renderer]
name = 'relative-cursor-'+args.renderer
ESC, CSI = '\x1b', '\x1b['
RESET = CSI+'65;1"p'+ESC+'c'+CSI+'?25l'
MARGINS = CSI+'4;17r'+CSI+'?69h'+CSI+'8;67s'
u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE


def exercise(hwnd, phase, current):
    pid = w.DWORD(); u.GetWindowThreadProcessId(hwnd, c.byref(pid))
    actual = int(u.GetPropW(hwnd, 'NemotermRenderer') or 0)
    assert actual in (1, 2, 3), actual
    if requested == 0: assert actual == 1
    if requested == 1 and os.environ.get('NEMOTERM_REQUIRE_OPENGL') == '1': assert actual == 2
    if requested == 2 and os.environ.get('NEMOTERM_REQUIRE_DIRECTX') == '1': assert actual == 3
    result = dict(actual_renderer=actual, pixel_checks=[], memory_acceptance=False,
                  memory_instrumented=actual != 1, clipboard_access=False, global_input=False)
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
            result['pixel_checks'].append(dict(name=label, sha256=hashlib.sha256(data).hexdigest()))
            return data

        expected = draw('absolute-outside-margins', RESET+CSI+'16;68HX'+CSI+'18;66HY')
        draw('relative-outside-margins', RESET+MARGINS+CSI+'16;66H'+CSI+'2aX'+CSI+'16;66H'+CSI+'2eY', expected)
        expected = draw('absolute-origin-clipped', RESET+CSI+'16;67HX'+CSI+'17;66HY')
        draw('relative-origin-clipped', RESET+MARGINS+CSI+'?6h'+CSI+'13;59H'+CSI+'2aX'+CSI+'13;59H'+CSI+'2eY', expected)
        expected = draw('double-width-reference', RESET+CSI+'7;1H'+ESC+'#6ABZ')
        draw('double-width-hidden-writes', RESET+CSI+'7;1H'+ESC+'#6AB'+CSI+'7;39H'+CSI+'4aQ中\u0301'+CSI+'7;3HZ', expected)

        before = [current()['columns'], current()['rows']]
        assert u.MoveWindow(terminal_host(hwnd), 50, 50, 780, 540, True)
        phase('resized-geometry', CSI+'18t', None)
        result['resized_grid'] = [current()['columns'], current()['rows']]
        assert result['resized_grid'] != before
        expected = draw('resized-double-width-reference', RESET+CSI+'7;1H'+ESC+'#6ABZ')
        draw('resized-saturated-position', RESET+CSI+'7;1H'+ESC+'#6AB'+CSI+'99999999999999999aQ中\u0301'+CSI+'7;3HZ', expected)
        if gpu: gpu.capture(name+'-window.png')
        else: capture(hwnd, name+'-window.png')
        return result
    finally:
        if gpu: gpu.close()


run(name, CASES, exercise=exercise, profile=dict(NemoRenderer=requested, MouseAutocopy=0, WarnOnClose=0),
    font=os.environ.get('NEMOTERM_TEST_FONT',
        'Consolas' if os.environ.get('CI') == 'true' else 'SarasaTermSC Nerd Font Light'))
