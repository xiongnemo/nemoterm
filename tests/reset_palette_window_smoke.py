"""Captured reset/reverse-colour replies and visible repaint checks in an owned job."""
import argparse
from reset_palette_oracle_cases import CASES
from protocol_oracle_window import run
from native_test_utils import capture, hashlib, u, k, c, w, time, wait_for, memory_sample, os
from gpu_capture import OwnedGPUCapture

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--renderer', choices=('gdi', 'directx', 'opengl'), default='gdi')
args = parser.parse_args()
requested = {'gdi': 0, 'opengl': 1, 'directx': 2}[args.renderer]
CSI, OSC, ST = '\x1b[', '\x1b]', '\x1b\\'
u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE


def exercise(hwnd, phase, current):
    pid = w.DWORD()
    u.GetWindowThreadProcessId(hwnd, c.byref(pid))
    handle = k.OpenProcess(0x410, False, pid.value)
    assert handle
    active = int(u.GetPropW(hwnd, 'NemotermRenderer') or 0)
    assert active in (1, 2, 3), active
    if requested == 0:
        assert active == 1
    if requested == 1 and os.environ.get('NEMOTERM_REQUIRE_OPENGL') == '1':
        assert active == 2
    if requested == 2 and os.environ.get('NEMOTERM_REQUIRE_DIRECTX') == '1':
        assert active == 3
    gpu = None
    evidence = dict(actual_renderer=active, pixel_checks=[], memory_samples=[],
                    memory_instrumented=active != 1)
    try:
        if active != 1:
            gpu = OwnedGPUCapture(pid.value, hwnd)

        def image():
            return gpu.capture(return_pixels=True) if gpu else capture(hwnd, return_pixels=True)

        def remember(name):
            time.sleep(.08)
            pixels = image()
            evidence['pixel_checks'].append(dict(name=name, sha256=hashlib.sha256(pixels).hexdigest()))
            evidence['memory_samples'].append(memory_sample(handle))
            return pixels

        # Dynamic colours survive both resets, while indexed/special colours
        # return to configured defaults. DECSTR must repaint retained cells.
        draw = (CSI+'?25l'+CSI+'2J'+CSI+'2;3H'+CSI+'31mIndexed 中文 e\u0301'+
                CSI+'0m'+CSI+'4;3H'+CSI+'1mSpecial colour'+CSI+'0m'+CSI+'6;3HDynamic colour')
        baseline_setup = ('\x1bc'+OSC+'10;#123456;#234567;#345678'+ST+
                          OSC+'106;0;1'+ST+draw)
        phase('reset-pixel-baseline', baseline_setup, '')
        baseline = remember('reset-baseline')
        mutation = OSC+'4;1;#00ff00'+ST+OSC+'5;0;#ff00ff'+ST
        for name, reset in (('decstr', CSI+'!p'), ('ris', '\x1bc')):
            phase(name+'-mutate', mutation, '')
            assert remember(name+'-changed') != baseline
            phase(name+'-restore', reset+(draw if name == 'ris' else CSI+'?25l'), '')
            wait_for(lambda: image() == baseline)
            assert remember(name+'-restored') == baseline

        # A cursor equal to the displayed foreground follows screen reverse.
        # Compare the automatic result with explicit cursor colours; a wrong
        # colour must visibly differ even when the window has an outline cursor.
        for name, start, reverse, normal in (
            ('foreground', '#123456', '#234567', '#123456'),
            ('background', '#234567', '#234567', '#123456'),
            ('independent', '#456789', '#456789', '#456789'),
        ):
            phase(name+'-cursor-setup', baseline_setup+CSI+'?25h'+CSI+'2 q'+
                  CSI+'10;3H'+OSC+'12;'+start+ST+CSI+'?5h', '')
            reversed_pixels = remember(name+'-reverse-automatic')
            phase(name+'-reverse-explicit', OSC+'12;'+reverse+ST, '')
            assert remember(name+'-reverse-explicit') == reversed_pixels
            phase(name+'-reverse-wrong', OSC+'12;#ff00ff'+ST, '')
            assert remember(name+'-reverse-wrong') != reversed_pixels
            phase(name+'-normal-automatic', OSC+'12;'+reverse+ST+CSI+'?5l', '')
            # PuTTY deliberately holds a short visual bell after a quick
            # reverse on/off. Let that documented animation finish.
            time.sleep(.3)
            normal_pixels = remember(name+'-normal-automatic')
            phase(name+'-normal-explicit', OSC+'12;'+normal+ST, '')
            assert remember(name+'-normal-explicit') == normal_pixels
            phase(name+'-normal-wrong', OSC+'12;#ff00ff'+ST, '')
            assert remember(name+'-normal-wrong') != normal_pixels
        evidence['peak_private_ws'] = max(s['private_ws'] for s in evidence['memory_samples'])
        evidence['peak_total_ws'] = max(s['total_ws'] for s in evidence['memory_samples'])
        if active == 1:
            assert evidence['peak_private_ws'] < 20_000_000, evidence
        if gpu:
            gpu.capture(f'reset-palette-{args.renderer}-window.png')
        else:
            capture(hwnd, f'reset-palette-{args.renderer}-window.png')
        return evidence
    finally:
        if gpu:
            gpu.close()
        k.CloseHandle(handle)


run('reset-palette-'+args.renderer, CASES, exercise=exercise,
    barrier=(CSI+'>q', b'\x1bP>|Nemoterm(PuTTY 0.85)\x1b\\'),
    profile=dict(NemoRenderer=requested, Colour5='187,187,187', WarnOnClose=0),
    font=os.environ.get('NEMOTERM_TEST_FONT', 'Consolas' if os.environ.get('CI') == 'true'
                        else 'SarasaTermSC Nerd Font Light'))
