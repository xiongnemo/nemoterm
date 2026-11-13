"""Rendition-stack wire and pixel checks in an owned single-image terminal job."""
from sgr_stack_oracle_cases import CASES
from sgr_stack_direct_cases import CASES as DIRECT
from protocol_oracle_window import run
from native_test_utils import (capture, hashlib, terminal_host, u, k, c, w,
                              wait_for, time, memory_sample)

CSI = '\x1b['
barrier = (CSI+'>q', b'\x1bP>|Nemoterm(PuTTY 0.85)\x1b\\')


def exercise(hwnd, phase, current):
    evidence, samples = {}, []
    pid = w.DWORD()
    u.GetWindowThreadProcessId(hwnd, c.byref(pid))
    handle = k.OpenProcess(0x410, False, pid.value)
    assert handle

    def pixels(name, sequence):
        phase(name, sequence, '')
        time.sleep(.08)
        result = capture(hwnd, return_pixels=True)
        evidence[name] = hashlib.sha256(result).hexdigest()
        samples.append(memory_sample(handle))
        return result

    def frame(style, suffix=''):
        return ('\x1bc'+CSI+'?25l\x1b]10;rgb:f/f/f\x07\x1b]11;rgb:0/0/0\x07'+
                CSI+'2J'+CSI+'2;2H'+CSI+style+'m'+suffix+' '*20)

    try:
        modern = pixels('modern-double', frame('4:2;58:2::255:0:0'))
        assert b'\xff\0\0' in (modern[i:i+3] for i in range(0, len(modern), 3))
        legacy = pixels('legacy-double', frame('21;58:2::255:0:0'))
        combined = pixels('combined-double', frame('4;21;58:2::255:0:0'))
        assert modern == legacy == combined, 'legacy double underline changed pixels'
        curly = pixels('curly', frame('4:3;58:2::255:0:0'))
        restored = pixels('pop-reveals-curly', frame('4:3;58:2::255:0:0',
                          CSI+'21#{'+CSI+'21m'+CSI+'#}'))
        assert restored == curly and curly != modern
        restored_all = pixels('pop-restores-color', frame('4:3;58:2::255:0:0',
                              CSI+'#{'+CSI+'0;58:5:7m'+CSI+'#}'))
        assert restored_all == curly
        plain = pixels('plain', frame('0'))
        reset = pixels('reset-both-underlines', frame('4;21;24'))
        assert reset == plain and plain != modern

        colors = '38:2::12:34:56;48:2::78:90:123'
        expected = pixels('inverse-colors', frame(colors+';7'))
        erased = pixels('erase-then-invert-colors', frame(colors)+CSI+'2;2H'+
                        CSI+'20X'+CSI+'2;2;2;21;7$r')
        assert expected == erased, 'erase lost foreground RGB used by later inverse'
        assert b'\x0c\x22\x38' in (erased[i:i+3] for i in range(0, len(erased), 3))

        baseline = pixels('read-only-scene', frame('4:3;21;58:2::255:0:0'))
        for index in range(30):
            phase('read-only-'+str(index), CSI+'#{'+CSI+'0m'+CSI+'#}'+
                  CSI+'2;2;2;21#|', CSI+'0;4:3;21;58:2::255:0:0m')
        assert capture(hwnd, return_pixels=True) == baseline
        evidence['read_only_repetitions'] = 30

        before = [current()['columns'], current()['rows']]
        assert u.MoveWindow(terminal_host(hwnd), 40, 40, 700, 500, True)
        wait_for(lambda: [current()['columns'], current()['rows']] != before)
        cols, rows = current()['columns'], current()['rows']
        phase('resized-corner', '\x1bc'+CSI+f'{rows};{cols}H'+CSI+'3;21;32mZ'+
              CSI+f'{rows};{cols};999999999999;999999999999#|'+CSI+'6n',
              CSI+'0;3;21;32m'+CSI+f'{rows};{cols}R')
        phase('origin-corner', CSI+f'2;{rows}r'+CSI+'?69h'+CSI+f'3;{cols}s'+CSI+'?6h'+
              CSI+f'{rows-1};{cols-2};{rows-1};{cols-2}#|', CSI+'0;3;21;32m')
        evidence['resized_grid'] = [cols, rows]
        pixels('gallery', '\x1bc'+CSI+'?25l'+CSI+'2;3HSGR STACK / RECTANGLE REPORTS'+
               CSI+'5;3H'+CSI+'4:3;58:2::255:80:80mCurly / 中文 e\u0301'+
               CSI+'#{'+CSI+'0;21;38:2::80:180:255m'+CSI+'8;3HDouble underline'+
               CSI+'#}'+CSI+'11;3HRestored style and color'+CSI+'0m')
        capture(hwnd, 'sgr-stack-window.png')
        evidence['memory_samples'] = samples
        evidence['peak_private_ws'] = max(s['private_ws'] for s in samples)
        evidence['peak_total_ws'] = max(s['total_ws'] for s in samples)
        assert evidence['peak_private_ws'] < 20_000_000, evidence
        return evidence
    finally:
        k.CloseHandle(handle)


run('sgr-stack', CASES, extra_cases=DIRECT, exercise=exercise, barrier=barrier,
    profile=dict(NemoAllowChecksum=1, BoldAsColour=1, WarnOnClose=0))
