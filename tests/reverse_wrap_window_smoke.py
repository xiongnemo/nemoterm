"""Reverse-wrap mode, cursor, cell and raster checks in an owned native job."""
from reverse_wrap_oracle_cases import CASES
from reverse_wrap_direct_cases import CASES as DIRECT
from protocol_oracle_window import run
from native_test_utils import capture, hashlib, time, terminal_host, u, wait_for

CSI = '\x1b['
FRAME = '\x1bc'+CSI+'?25l'


def exercise(hwnd, phase, current):
    evidence = {}

    def pixels(name, sequence):
        phase(name, sequence, '')
        time.sleep(.08)
        value = capture(hwnd, return_pixels=True)
        evidence[name] = hashlib.sha256(value).hexdigest()
        return value

    baseline = pixels('wrapped-edit-baseline', FRAME+CSI+'2;79HAZ'+CSI+'3;1HBC')
    actual = pixels('wrapped-backspace-edit', FRAME+CSI+'?45h'+CSI+'2;79HAXBC'+'\b'*3+'Z')
    assert actual == baseline
    baseline = pixels('default-hard-edge-baseline', FRAME+CSI+'2;1HOLD'+CSI+'3;1HZ')
    actual = pixels('default-backspace-stops', FRAME+CSI+'2;1HOLD'+CSI+'3;1H\bZ')
    assert actual == baseline
    baseline = pixels('extended-hard-edge-baseline', FRAME+CSI+'2;80HZ')
    actual = pixels('extended-backspace-crosses', FRAME+CSI+'?1045h'+CSI+'3;1H\bZ')
    assert actual == baseline
    baseline = pixels('margin-edit-baseline', FRAME+CSI+'3;5HABCDZF'+CSI+'4;5HGHIJKL'+CSI+'5;5HM')
    actual = pixels('margin-wrapped-edit', FRAME+CSI+'?45;69h'+CSI+'5;10s'+CSI+'3;6r'+CSI+'3;5HABCDEFGHIJKLM'+CSI+'9DZ')
    assert actual == baseline

    baseline = pixels('read-only-scene', FRAME+CSI+'2;80Hx\u0301BC'+CSI+'8;4H'+
        '\x1bP0;1q#1;2;100;0;0!24~\x1b\\'+CSI+'?45h')
    for i in range(30):
        phase(f'read-only-{i}', CSI+'3;3H'+CSI+'3D'+CSI+'6n',CSI+'2;80R')
    assert capture(hwnd, return_pixels=True) == baseline
    evidence['read_only_repetitions'] = 30

    before = [current()['columns'],current()['rows']]
    assert u.MoveWindow(terminal_host(hwnd),40,40,1000,600,True)
    wait_for(lambda: [current()['columns'],current()['rows']] != before)
    columns,rows = current()['columns'],current()['rows']
    phase('resized-extended-cycle', FRAME+CSI+'?1045h'+CSI+'1;1H\b'+CSI+'6n',f'{CSI}{rows};{columns}R')
    phase('resized-mode-retained',CSI+'?1045$p',CSI+'?1045;1$y')
    evidence['resized_grid'] = [columns,rows]
    pixels('gallery',FRAME+CSI+'2;3HREVERSE WRAP / CURSOR AND PIXEL CHECKS'+CSI+'5;3H'+
           CSI+'36m中文 x\u0301  /  BS, CUB, margins, resize'+CSI+'0m')
    capture(hwnd,'reverse-wrap-window.png')
    return evidence


run('reverse-wrap',CASES,extra_cases=DIRECT,exercise=exercise,
    barrier=(CSI+'>q',b'\x1bP>|Nemoterm(PuTTY 0.85)\x1b\\'),
    profile=dict(NemoAllowChecksum=1,WarnOnClose=0))
