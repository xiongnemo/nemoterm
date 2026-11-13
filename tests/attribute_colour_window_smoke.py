"""Prepared owned-window attribute-colour checks; local runtime still paused.

Compare rendered attribute colours with an explicit-RGB reference scene. No
clipboard imports, global input or interaction with unrelated windows.
"""
import argparse
from attribute_colour_cases import CASES, CSI, OSC, ST, COLORS, SET, command
from protocol_oracle_window import run
from native_test_utils import (capture, hashlib, terminal_host, u, k, c, w,
                              wait_for, time, memory_sample, os)
from gpu_capture import OwnedGPUCapture

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--renderer', choices=('gdi', 'directx', 'opengl'), default='gdi')
parser.add_argument('--configured', action='store_true', help='Verify saved startup modes and colour defaults')
args = parser.parse_args()
requested = {'gdi': 0, 'opengl': 1, 'directx': 2}[args.renderer]
test_name = 'attribute-colour-'+args.renderer+('-configured' if args.configured else '')
u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE
MODES_OFF = command(6, '0;0;1;0;2;0;3;0;4;0;5;0')
MODES_ON = command(106, '0;1;1;1;2;1;3;1;4;1;5;0')
TEXT = 'Colour 中文 e\u0301 0123456789'
CLEAR = CSI+'0m'+CSI+'?25l'+CSI+'2J'


def scene(reference=False, set_modes=True):
    result = ((MODES_OFF if reference else MODES_ON) if set_modes else '')+CLEAR
    styles = ['1', '4:3', '5', '7', '3', '1;3;4;5',
              '1;38;2;18;52;86', '7;48;2;16;32;48']
    for i, style in enumerate(styles):
        if reference:
            fg = COLORS[i] if i < 5 and i != 3 else '778899' if i == 5 else '123456' if i == 6 else 'ffffff'
            bg = COLORS[3] if i == 3 else '102030' if i == 7 else '000000'
            rgb = lambda value: ';'.join(str(int(value[n:n+2], 16)) for n in (0, 2, 4))
            style = '38;2;'+rgb(fg)+';48;2;'+rgb(bg)
        result += CSI+f'{i+2};3H'+CSI+'0;'+style+'m'+TEXT
    return result+CSI+'0m'


def exercise(hwnd, phase, current):
    pid = w.DWORD(); u.GetWindowThreadProcessId(hwnd, c.byref(pid))
    active = int(u.GetPropW(hwnd, 'NemotermRenderer') or 0)
    assert active in (1, 2, 3), active
    if requested == 0: assert active == 1
    if requested == 1 and os.environ.get('NEMOTERM_REQUIRE_OPENGL') == '1': assert active == 2
    if requested == 2 and os.environ.get('NEMOTERM_REQUIRE_DIRECTX') == '1': assert active == 3
    handle = k.OpenProcess(0x410, False, pid.value); assert handle
    gpu = None
    evidence = dict(actual_renderer=active, pixel_checks=[], memory_samples=[],
                    memory_instrumented=active != 1, clipboard_access=False,
                    configured_defaults=args.configured)
    try:
        if active != 1: gpu = OwnedGPUCapture(pid.value, hwnd)
        def pixels():
            return gpu.capture(return_pixels=True) if gpu else capture(hwnd, return_pixels=True)
        def remember(name):
            time.sleep(.08)
            data = pixels()
            evidence['pixel_checks'].append(dict(name=name, sha256=hashlib.sha256(data).hexdigest()))
            evidence['memory_samples'].append(memory_sample(handle))
            return data
        def equal(expected):
            wait_for(lambda: pixels() == expected)

        if args.configured:
            phase('saved-startup-scene', scene(set_modes=False), '')
            startup = remember('saved-startup-modes-and-colours')
        phase('explicit-reference', command(10, '#ffffff;#000000')+SET+scene(True), '')
        expected = remember('explicit-rgb-reference')
        if args.configured: assert startup == expected
        phase('attribute-scene', scene(), '')
        equal(expected); assert remember('attribute-equivalence') == expected
        phase('save-change', CSI+'1#P'+command(5, '0;red;3;blue'), '')
        assert remember('changed-colours') != expected
        phase('restore', CSI+'1#Q', '')
        equal(expected)
        phase('sync-disable', CSI+'?2026h'+command(6, '0;0'), '')
        assert remember('frozen-mode-change') == expected
        phase('sync-commit', CSI+'?2026l', '')
        assert remember('committed-mode-change') != expected
        phase('mode-restore', MODES_ON, ''); equal(expected)

        # Reset of colour values must not reset enable/override modes.
        phase('reset-special', command(105), '')
        reset = remember('special-reset')
        if args.configured: assert reset == expected
        else: assert reset != expected
        phase('restore-special', SET, ''); equal(expected)
        old_size = [current()['columns'], current()['rows']]
        assert u.MoveWindow(terminal_host(hwnd), 50, 50, 780, 540, True)
        wait_for(lambda: [current()['columns'], current()['rows']] != old_size)
        phase('resized-reference', scene(True), '')
        resized = remember('resized-explicit-reference')
        phase('resized-attributes', scene(), '')
        equal(resized); assert remember('resized-equivalence') == resized
        for index in range(20):
            phase('bounded-'+str(index), (CSI+'1#P'+command(5, '0;red;3;blue')+CSI+'1#Q')*50, '')
            evidence['memory_samples'].append(memory_sample(handle))
        equal(resized)
        evidence['repeated_save_restore'] = 1000
        evidence['peak_private_ws'] = max(s['private_ws'] for s in evidence['memory_samples'])
        if active == 1: assert evidence['peak_private_ws'] < 20_000_000, evidence
        name = test_name+'-window.png'
        if gpu: gpu.capture(name)
        else: capture(hwnd, name)
        return evidence
    finally:
        if gpu: gpu.close()
        k.CloseHandle(handle)


profile = dict(NemoRenderer=requested, MouseAutocopy=0, WarnOnClose=0,
               Colour0='255,255,255', Colour2='0,0,0')
if args.configured:
    profile.update(NemoAttributeCustomColours=31, NemoAttributeColourModes=31,
                   NemoAttributeKeepStyles=0)
    for name, colour in zip(('Bold', 'Underline', 'Blink', 'Reverse', 'Italic'), COLORS):
        profile['NemoAttribute'+name+'Colour'] = int(colour, 16)

run(test_name, (), extra_cases=() if args.configured else CASES, exercise=exercise,
    source_reference='XTerm(412) capture 43454910323; strict index parsing and selective reset divergences documented',
    barrier=(CSI+'>q', b'\x1bP>|Nemoterm(PuTTY 0.85)\x1b\\'),
    profile=profile,
    font=os.environ.get('NEMOTERM_TEST_FONT',
        'Consolas' if os.environ.get('CI') == 'true' else 'SarasaTermSC Nerd Font Light'))
