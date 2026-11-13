"""Rectangle checksum replies and read-only rendering through the owned host."""
from checksum_oracle_cases import CASES
from checksum_direct_cases import CASES as DIRECT
from protocol_oracle_window import run
from native_test_utils import capture, hashlib, terminal_host, u, wait_for, time

barrier = ('\x1b[>q', b'\x1bP>|Nemoterm(PuTTY 0.85)\x1b\\')


def exercise(hwnd, phase, current):
    evidence = {}
    phase('reset-geometry', '\x1bc', '')
    before = [current()['columns'], current()['rows']]
    assert u.MoveWindow(terminal_host(hwnd), 40, 40, 700, 500, True)
    wait_for(lambda: [current()['columns'], current()['rows']] != before)
    cols, rows = current()['columns'], current()['rows']
    phase('resized-corner', f'\x1b[{rows};{cols}HZ\x1b[23#y'
          f'\x1b[7;1;{rows};{cols};999999999999;999999999999*y\x1b[6n',
          f'\x1bP7!~005A\x1b\\\x1b[{rows};{cols}R')
    phase('origin-corner', f'\x1b[2;{rows}r\x1b[?69h\x1b[3;{cols}s\x1b[?6h'
          f'\x1b[7;1;{rows-1};{cols-2};{rows-1};{cols-2}*y', '\x1bP7!~005A\x1b\\')
    evidence['resized_grid'] = [cols, rows]
    phase('visible-scene', '\x1bc\x1b[?25l\x1b[2;3H\x1b[36m'
          'CHECKSUM / content preserved / 中 e\u0301\x1b[0m'
          '\x1b[5;3H\x1b[?80h\x1bP0;1q#1;2;100;0;0!30~\x1b\\', '')
    time.sleep(.2)
    before_pixels = capture(hwnd, return_pixels=True)
    reply = phase('screen-checksum', f'\x1b[23#y\x1b[7;1;1;1;{rows};{cols}*y', None)
    assert len(reply) == 11 and reply.startswith(b'\x1bP7!~') and reply.endswith(b'\x1b\\')
    for index in range(40):
        phase('repeat-'+str(index), f'\x1b[7;1;1;1;{rows};{cols}*y', reply.decode())
    after_pixels = capture(hwnd, 'checksum-window.png', return_pixels=True)
    assert before_pixels == after_pixels
    evidence['content_rgb_sha256'] = hashlib.sha256(after_pixels).hexdigest()
    evidence['read_only_repeats'] = 40
    return evidence


run('checksum-disabled', [], extra_cases=[('default-denied', 'A\x1b[23#y\x1b[7;1;1;1;1;1*y', '')],
    barrier=barrier, profile={})
run('checksum', CASES, extra_cases=DIRECT, exercise=exercise, barrier=barrier,
    profile=dict(NemoAllowChecksum=1, UTF8linedraw=1, WarnOnClose=0))
