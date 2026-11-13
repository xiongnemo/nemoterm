"""Graphics capability replies, live geometry and palette pixels through ConPTY."""
import re
from protocol_oracle_window import run
from graphics_query_oracle_cases import CASES
from native_test_utils import capture, hashlib, terminal_host, u, wait_for

direct = [
    ('implemented-defaults', '\x1b[?1;2;0S\x1b[?1;4;0S\x1b[?2;4;0S',
     '\x1b[?1;0;256S\x1b[?1;0;256S\x1b[?2;0;8192;8192S'),
    ('implemented-register-limit', '\x1b[?1;3;257S\x1b[?1;3;1024S\x1b[?1;1;0S',
     '\x1b[?1;3S\x1b[?1;3S\x1b[?1;0;256S'),
    ('omitted-item', '\x1b[?;1;0S', '\x1b[?0;1S'),
]


def exercise(hwnd, phase, current):
    evidence = {}

    def geometry(name):
        wire = phase(name, '\x1b[16t\x1b[18t\x1b[?2;1;0S\x1b[?2;4;0S', None)
        match = re.fullmatch(rb'\x1b\[6;(\d+);(\d+)t\x1b\[8;(\d+);(\d+)t'
            rb'\x1b\[\?2;0;(\d+);(\d+)S\x1b\[\?2;0;8192;8192S', wire)
        assert match, (name, wire)
        ch, cw, rows, cols, width, height = map(int, match.groups())
        assert (width, height) == (min(cols*cw, 8192), min(rows*ch, 8192)), wire
        assert (cols, rows) == (current()['columns'], current()['rows'])
        evidence[name] = dict(cell=[cw, ch], grid=[cols, rows], graphics=[width, height])
        return cols, rows

    before = geometry('initial-geometry')
    assert u.MoveWindow(terminal_host(hwnd), 40, 40, 700, 500, True)
    wait_for(lambda: (current()['columns'], current()['rows']) != before)
    after = geometry('resized-geometry')
    assert before != after

    # At two registers, #2 aliases #0: the entire 32x12 raster is red.
    # At 256 registers, #0 stays black: only its right half is red.
    payload = '\x1bP0;1q"1;1;32;12#2;2;100;0;0' + \
        '#0!16~#2!16~-#0!16~#2!16~\x1b\\'

    def pixels(name, red_count):
        last = None
        def matches():
            nonlocal last
            last = capture(hwnd, return_pixels=True)
            return sum(last[i:i+3] == b'\xff\0\0'
                       for i in range(0, len(last), 3)) == red_count
        try:
            wait_for(matches)
        except AssertionError:
            capture(hwnd, 'graphics-query-failure.png')
            raise
        evidence[name] = dict(red_pixels=red_count, rgb_sha256=hashlib.sha256(last).hexdigest())
        return last

    phase('two-register-raster', '\x1bc\x1b[?25l\x1b[?80h\x1b[?1070h'
          '\x1b[?1;3;2S\x1b[2J\x1b[H'+payload, '\x1b[?1;0;2S')
    old_pixels = pixels('two-register-pixels', 384)
    phase('retain-existing-raster', '\x1b[?1;3;256S', '\x1b[?1;0;256S')
    assert pixels('retained-pixels', 384) == old_pixels
    phase('new-256-register-raster', '\x1b[2J\x1b[H'+payload, '')
    pixels('new-256-register-pixels', 192)
    capture(hwnd, 'graphics-query-window.png')
    return evidence


run('graphics-query', CASES, extra_cases=direct, exercise=exercise)
