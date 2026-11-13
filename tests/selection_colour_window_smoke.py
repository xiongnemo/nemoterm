"""Owned-window selection colours, with no clipboard imports or copy actions.

This new fixture has not been run locally. Authored protocol expectations are
kept separate from the pending independent XTerm capture.
"""
import argparse
from selection_colour_cases import CASES, CSI, OSC, ST
from protocol_oracle_window import run
from native_test_utils import (capture, hashlib, terminal_host, u, k, c, w,
                              wait_for, time, memory_sample, os)
from gpu_capture import OwnedGPUCapture

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--renderer', choices=('gdi', 'directx', 'opengl'), default='gdi')
parser.add_argument('--configured', action='store_true',
                    help='Use saved custom selection defaults instead of inverse video')
args = parser.parse_args()
requested = {'gdi': 0, 'opengl': 1, 'directx': 2}[args.renderer]
test_name = 'selection-colour-'+args.renderer+('-configured' if args.configured else '')
u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE

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
        def matches(expected):
            return wait_for(lambda: pixels() == expected)
        def select(rectangular=False):
            value = current()
            rect = w.RECT(); assert u.GetClientRect(hwnd, c.byref(rect))
            cw, ch = (rect.right-2)//value['columns'], (rect.bottom-2)//value['rows']
            def point(col, row):
                return ((1+col*cw+cw//2) & 0xffff) | ((1+row*ch+ch//2) << 16)
            modifiers = 4 | (8 if rectangular else 0)  # Shift; Ctrl adds rectangle.
            u.SendMessageW(hwnd, 0x201, modifiers | 1, point(2, 1))
            u.SendMessageW(hwnd, 0x200, modifiers | 1, point(20, 3 if rectangular else 1))
            u.SendMessageW(hwnd, 0x202, modifiers, point(20, 3 if rectangular else 1))

        scene = ('\x1bc'+CSI+'?5l'+OSC+'117'+ST+OSC+'119'+ST+
                 OSC+'10;#ffffff;#000000'+ST+CSI+'?25l'+CSI+'2J'+CSI+'2;3H'+
                 CSI+'38;2;16;32;48;48;2;64;80;96mSEL 中文 e\u0301 0123456789'+
                 CSI+'0m'+CSI+'4;3H'+CSI+'4:3mRECTANGLE UNDERLINE'+CSI+'0m'+
                 CSI+'6;3H\x1bP0;1q"1;1;40;24#1;2;0;100;0#1'+('!40~-')*4+ST)
        phase('scene', scene, '')
        unselected = remember('unselected')
        select()
        wait_for(lambda: pixels() != unselected)
        baseline = remember('default-selection')
        phase('set-selection-colours', OSC+'17;#112233;;#aabbcc'+ST, '')
        custom = remember('custom-selection'); assert custom != baseline
        # Background pixels do not depend on glyph antialiasing.
        assert sum(custom[i:i+3] == b'\x11\x22\x33' for i in range(0, len(custom), 3)) > 40
        phase('stack-change', CSI+'1#P'+OSC+'17;red;;blue'+ST, '')
        assert remember('changed-selection') != custom
        phase('stack-restore', CSI+'1#Q', '')
        matches(custom); assert remember('restored-selection') == custom

        phase('sync-change', CSI+'?2026h'+OSC+'17;red;;blue'+ST, '')
        assert remember('frozen-selection') == custom
        phase('sync-commit', CSI+'?2026l', '')
        assert remember('committed-selection') != custom
        phase('sync-restore', CSI+'1#Q', ''); matches(custom)
        phase('reset-background', OSC+'117'+ST+OSC+'19;?'+ST,
              OSC+'19;rgb:aaaa/bbbb/cccc'+ST)
        partial = remember('background-reset'); assert partial not in (custom, baseline)
        phase('reset-foreground', OSC+'119'+ST, '')
        matches(baseline); assert remember('both-reset') == baseline

        old_size = [current()['columns'], current()['rows']]
        assert u.MoveWindow(terminal_host(hwnd), 50, 50, 780, 540, True)
        wait_for(lambda: [current()['columns'], current()['rows']] != old_size)
        phase('resize-scene', scene, '')
        time.sleep(.6)  # Distinguish a new drag from the previous multi-click chain.
        select(rectangular=True)
        rectangular = remember('rectangular-default')
        phase('rectangle-custom', OSC+'17;#112233;;#aabbcc'+ST, '')
        rectangle_custom = remember('rectangular-custom'); assert rectangle_custom != rectangular
        phase('rectangle-reset', OSC+'117'+ST+OSC+'119'+ST, '')
        matches(rectangular)
        for index in range(20):
            phase('bounded-selection-'+str(index),
                  (CSI+'1#P'+OSC+'17;red;;blue'+ST+CSI+'1#Q')*50, '')
            evidence['memory_samples'].append(memory_sample(handle))
        matches(rectangular)
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

run(test_name, (), extra_cases=CASES, exercise=exercise,
    source_reference='Authored specification/source expectations; XTerm capture pending',
    barrier=(CSI+'>q', b'\x1bP>|Nemoterm(PuTTY 0.85)\x1b\\'),
    profile=dict(NemoRenderer=requested, MouseAutocopy=0, WarnOnClose=0,
                 NemoSelectionBackgroundEnabled=int(args.configured),
                 NemoSelectionForegroundEnabled=int(args.configured),
                 NemoSelectionBackground=0x224488, NemoSelectionForeground=0xddeeff),
    font=os.environ.get('NEMOTERM_TEST_FONT',
        'Consolas' if os.environ.get('CI') == 'true' else 'SarasaTermSC Nerd Font Light'))
