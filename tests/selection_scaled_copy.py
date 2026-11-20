"""Shift-copy must not include characters pushed beyond the window by DEC line sizing."""
from native_test_utils import u, wait_for


def verify(hwnd, begin, point, capture, tile, copy, barrier, evidence, desktop=None):
    checks = evidence['scaled_copy_system' if desktop else 'scaled_copy_messages'] = []
    hidden = 'OFFSCREEN'
    ack = '1b5b306e'
    for i, (name, mode, tail, reverse) in enumerate((
        ('normal-control', '5', 'WXYZ', False),
        ('double-width', '6', 'WXYZ', False),
        ('upper-half-reverse', '3', 'WXYZ', True),
        ('lower-half-spaces', '4', 'W   ', False),
    )):
        if desktop and mode != '6': continue
        y = 5 if i % 2 == 0 else 13
        tag = ('system-' if desktop else '') + 'scaled-copy-' + name
        xy = lambda x, row: f'\x1b[{row+1};{x+1}H'
        prefix = '0123456789' * 3 + 'abcdef' + tail
        marked = '\x1b[44m' + prefix + '\x1b[41m' + hidden + '\x1b[0m'
        # This separate row never contains the hidden marker in a scaled case.
        # Matching its entire 80-cell image proves exactly what was visible.
        reference = marked if mode == '5' else '\x1b[44m' + prefix + '\x1b[0m'
        begin(tag+'-source', '\x1bc\x1b[?25l'+xy(0,y)+marked+xy(0,y+1)+'END|'+
              xy(0,y+3)+reference+'\x1b[?1002;1006h')
        def has_marker():
            p = capture(return_pixels=True)
            return tile(p,40,y) != tile(p,52,y) and tile(p,39,y) != tile(p,40,y)
        wait_for(has_marker)
        modes = begin(tag+'-size', xy(0,y)+'\x1b#'+mode+xy(0,y+3)+'\x1b#'+mode+
                      '\x1b[?1002$p\x1b[?1006$p', preserve_mouse=True)
        assert modes['hex'] == '1b5b3f313030323b3124791b5b3f313030363b312479' + ack, modes
        def painted():
            p = capture(return_pixels=True)
            if mode != '5' and tile(p,79,y)==tile(p,79,y+2): return None
            return p if all(tile(p,x,y)==tile(p,x,y+3) for x in range(80)) else None
        before = wait_for(painted); capture(tag+'-source.png')
        # Start on the final four *visible* characters of the scaled row.
        left = 36 if mode == '5' else 72
        a,b = point(left,y),point(2,y+1)
        if reverse: a,b = b,a
        begin(tag+'-gesture','',preserve_mouse=True)
        if desktop:
            desktop.point(a&65535,a>>16); desktop.event(0x10,True); desktop.event(None,True)
            try:
                wait_for(lambda: desktop.state().capture==hwnd)
                desktop.point(b&65535,b>>16); desktop.event(None,False)
            finally:
                for key in reversed(desktop.held[:]): desktop.event(key,False)
        else:
            u.SendMessageW(hwnd,0x201,5,a); u.SendMessageW(hwnd,0x200,5,b); u.SendMessageW(hwnd,0x202,4,b)
        def changes(p):
            return [[x for x in range(80) if tile(before,x,row)!=tile(p,x,row)] for row in (y,y+1)]
        want_cells = [list(range(left,80)),[0,1,2]]
        wait_for(lambda: bool(changes(capture(return_pixels=True))[1]))
        cells = changes(capture(tag+'-marked.png',return_pixels=True))
        wanted = (tail+hidden if mode=='5' else tail.rstrip())+'\r\nEND'
        got = copy(); wire = barrier(None)
        checks.append(dict(case=name, copied=got, expected=wanted, highlight=cells, expected_cells=want_cells,
                           raw_input=wire, passed=cells==want_cells and got==wanted and wire==ack*2))
    return all(r['passed'] for r in checks)
