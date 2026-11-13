"""Presentation reports, replay, character-set pixels and resize in an owned job."""
from presentation_state_oracle_cases import CASES
from presentation_state_direct_cases import CASES as DIRECT
from protocol_oracle_window import run
from native_test_utils import capture, hashlib, terminal_host, u, wait_for, time

CSI, DCS, ST = '\x1b[', '\x1bP', '\x1b\\'
barrier = (CSI+'>q', b'\x1bP>|Nemoterm(PuTTY 0.85)\x1b\\')
frame = '\x1bc'+CSI+'?25l'+CSI+'2;2H'


def exercise(hwnd, phase, current):
    evidence = {}

    def pixels(name, text):
        phase(name, text, '')
        time.sleep(.08)
        result = capture(hwnd, return_pixels=True)
        evidence[name] = hashlib.sha256(result).hexdigest()
        return result

    normal = pixels('ordinary-q', frame+'qqqq')
    expected = pixels('g0-lines', frame+'\x1b(0q\x1b(Bq\x1b(0qq')
    actual = pixels('g2-single-and-locking', frame+'\x1b*0\x1bNqq\x1bnqq')
    assert actual == expected and actual != normal
    actual = pixels('g3-single-and-locking', frame+'\x1b+0\x1bOqq\x1boqq')
    assert actual == expected

    expected = pixels('cursor-style-baseline', frame+CSI+'1;4;7m'+' '*20)
    report = phase('capture-cursor', frame+CSI+'1;4;7m'+CSI+'1$w',
                   DCS+'1$u2;2;1;K;@;@;0;2;@;BBBB'+ST)
    restored = report.replace(b'1$u', b'1$t', 1).decode()
    actual = pixels('replay-cursor', CSI+'0m'+CSI+'18;50H'+restored+' '*20)
    assert actual == expected, 'replayed cursor rendition or position changed pixels'

    baseline_tabs = DCS+'2$u9/17/25/33/41/49/57/65/73'+ST
    report = phase('capture-tabs', '\x1bc'+CSI+'2$w', baseline_tabs)
    phase('mutate-tabs', DCS+'2$t2/7/37'+ST+CSI+'2$w', DCS+'2$u2/7/37'+ST)
    phase('replay-tabs', report.replace(b'2$u', b'2$t', 1).decode()+CSI+'2$w', baseline_tabs)

    phase('prepare-hidden-tab', DCS+'2$t100'+ST+CSI+'2$w', DCS+'2$u'+ST)
    before = [current()['columns'], current()['rows']]
    assert u.MoveWindow(terminal_host(hwnd), 40, 40, 1000, 600, True)
    wait_for(lambda: current()['columns'] >= 100 and
             [current()['columns'], current()['rows']] != before)
    cols, rows = current()['columns'], current()['rows']
    phase('resized-hidden-tab', CSI+'2$w'+CSI+'"v',
          DCS+'2$u100'+ST+CSI+f'{rows};{cols};1;1;1"w')
    phase('origin-absolute-cursor', CSI+f'3;{rows}r'+CSI+'?69h'+CSI+f'11;{cols}s'+
          CSI+'?6h'+CSI+'5;7H'+CSI+'1$w', DCS+'1$u7;17;1;@;@;A;0;2;@;BBBB'+ST)
    evidence['resized_grid'] = [cols, rows]

    baseline = pixels('read-only-scene', frame+CSI+'36mPresentation state / 中文 e\u0301'+CSI+'0m')
    reply = phase('read-only-capture', CSI+'1$w'+CSI+'2$w'+CSI+'"v', None)
    for index in range(30):
        phase('read-only-'+str(index), CSI+'1$w'+CSI+'2$w'+CSI+'"v', reply.decode())
    assert capture(hwnd, return_pixels=True) == baseline
    evidence['read_only_repetitions'] = 30
    blank = pixels('protection-blank', frame)
    protected = pixels('protected-text-and-sixel', frame+CSI+'1"qABC'+CSI+'2;2H'+
                       DCS+'0;1q#1;2;100;0;0!24~'+ST)
    assert protected != blank
    pixels('soft-reset-keeps-content', CSI+'!p'+CSI+'?25l')
    erased = pixels('soft-reset-selective-erase', CSI+'?2J')
    assert erased == blank, 'ended protection family still prevented text/image erasure'
    pixels('gallery', frame+'PRESENTATION STATE / CAPTURE AND RESTORE'+
           CSI+'5;3H'+CSI+'36mG2: '+ '\x1b*0\x1bnlqqqk\x0f'+
           CSI+'7;3HG3: '+ '\x1b+0\x1bolqqqk\x0f'+
           CSI+'10;3H'+CSI+'0mCursor and tab reports survived replay and resize')
    capture(hwnd, 'presentation-state-window.png')
    return evidence


run('presentation-state', CASES, extra_cases=DIRECT, exercise=exercise,
    barrier=barrier, profile=dict(UTF8linedraw=1, NemoAllowChecksum=1, WarnOnClose=0))
