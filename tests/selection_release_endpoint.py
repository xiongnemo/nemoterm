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
