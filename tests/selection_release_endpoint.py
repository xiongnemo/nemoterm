"""Check the release cell independently of the most recent WM_MOUSEMOVE."""
from native_test_utils import u, time, wait_for
from clipboard_test_utils import clipboard_text


def verify_release_endpoint(hwnd, begin, point, capture, tile, shortcut, barrier, evidence):
    rows = ('ABCDEFGHIJ', 'klmnopqrst')
    top = 7
    cases = [
        ('forward', (2, 0), (4, 0), (6, 0), False, 'CDEFG', [(x, 0) for x in range(2, 7)]),
        ('backward', (8, 1), None, (3, 1), False, 'nopqrs', [(x, 1) for x in range(3, 9)]),
        ('block', (2, 0), (3, 1), (5, 1), True, 'CDEF\r\nmnop', [(x, y) for y in range(2) for x in range(2, 6)]),
        ('stationary', (9, 1), None, (9, 1), False, None, []),
    ]
    observations = evidence['release_endpoints'] = []
    def coord(pt): return point(pt[0], top + pt[1])
    for name, press, move, release, block, expected, cells in cases:
        begin('release-endpoint-' + name, '\x1bc\x1b[?25l\x1b[2J\x1b[8;1H' + '\r\n'.join(rows) + '\x1b[?1002;1006h')
        def source():
            pixels = capture(return_pixels=True)
            return pixels if all(len(set(tile(pixels, x, y+top))) > 1 for y in range(2) for x in range(10)) else None
        before = wait_for(source)
        u.SendMessageW(hwnd, 0x201, 13 if block else 5, coord(press))
        if move is not None: u.SendMessageW(hwnd, 0x200, 1, coord(move))
        u.SendMessageW(hwnd, 0x202, 0, coord(release))  # modifiers already released
        wire = barrier()  # synchronise with the child; mouse reports must be absent
        def changed(pixels):
            return [(x,y) for y in range(2) for x in range(10) if tile(before,x,y+top) != tile(pixels,x,y+top)]
        until = time.monotonic() + 2
        while changed(capture(return_pixels=True)) != cells and time.monotonic() < until:
            time.sleep(.04)
        actual = changed(capture('selection-release-' + name + '.png', return_pixels=True))
        seq = u.GetClipboardSequenceNumber()
        if expected is not None: shortcut(67,46)
        copied = clipboard_text(hwnd) if expected is not None and u.GetClipboardSequenceNumber() != seq else None
        observations.append(dict(case=name, press=press, move=move, release=release, selected_cells=actual,
                                 expected_cells=cells, copied=copied, expected_text=expected, child_hex=wire,
                                 passed=actual==cells and copied==expected))
    assert all(row['passed'] for row in observations), observations


def verify_wide_boundary(hwnd, begin, point, capture, tile, shortcut, barrier, evidence):
    # In the first row, 中 spans columns 1 and 2, and the decomposed e occupies 3.
    # On the other row every character is narrow: a rectangle must not widen it.
    observations = evidence['wide_boundaries'] = []
    cases = [
        ('start-on-trailer', (2,0), (3,0), False, '中e\u0301', [[1,2,3],[]]),
        ('end-on-trailer-backwards', (4,0), (2,0), False, '中e\u0301Z', [[1,2,3,4],[]]),
        ('end-on-leader', (0,0), (1,0), False, 'A中', [[0,1,2],[]]),
        ('two-halves', (1,0), (2,0), False, '中', [[1,2],[]]),
        ('block-trailer', (2,0), (3,1), True, '中e\u0301\r\nCD', [[1,2,3],[2,3]]),
        ('block-one-column', (2,1), (2,0), True, '中\r\nC', [[1,2],[2]]),
        ('block-leader', (1,1), (1,0), True, '中\r\nB', [[1,2],[1]]),
        ('supplementary-first', (0,0), (3,0), False, 'L\U00010000\U00010001Y', [[0,1,2,3],[]]),
    ]
    for i,(name,anchor,end,block,wanted,cells) in enumerate(cases):
        top=9 if i%2==0 else 13
        first='L\U00010000\U00010001YZ|' if name=='supplementary-first' else 'A中e\u0301Z|'
        begin('wide-boundary-'+name,'\x1bc\x1b[?25l\x1b[2J'+f'\x1b[{top+1};1H'+
              first+'\r\nABCDEF\x1b[?1002;1006h')
        def source():
            pixels=capture(return_pixels=True)
            return pixels if all(len(set(tile(pixels,x,top+y)))>1 for x,y in ((0,0),(3,0),(5,0),(5,1))) else None
        before=wait_for(source)
        def coord(p): return point(p[0],top+p[1])
        u.SendMessageW(hwnd,0x201,13 if block else 5,coord(anchor))
        u.SendMessageW(hwnd,0x200,1,coord(end)); u.SendMessageW(hwnd,0x202,0,coord(end))
        wire=barrier()
        def changed(p):return [[x for x in range(6) if tile(p,x,top+y)!=tile(before,x,top+y)] for y in range(2)]
        until=time.monotonic()+1
        while changed(capture(return_pixels=True))!=cells and time.monotonic()<until:time.sleep(.04)
        actual=changed(capture('selection-wide-'+name+'.png',return_pixels=True))
        previous=u.GetClipboardSequenceNumber();shortcut(67,46)
        copied=clipboard_text(hwnd) if u.GetClipboardSequenceNumber()!=previous else None
        observations.append(dict(case=name,anchor=anchor,end=end,rectangle=block,child_hex=wire,
            expected_text=wanted,copied=copied,expected_cells=cells,selected_cells=actual,
            passed=copied==wanted and actual==cells))
    assert all(row['passed'] for row in observations), observations
