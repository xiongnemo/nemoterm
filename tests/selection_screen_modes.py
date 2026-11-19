"""Keep Shift selection only while its displayed text buffer survives a DEC mode request."""
from native_test_utils import u, wait_for, time
from clipboard_test_utils import clipboard_text


def verify(hwnd, begin, point, capture, tile, barrier, desktop, evidence):
    rows = evidence['screen_selection'] = []
    ack = b'\x1b[0n'
    pattern = '\x1b[7;1H|ABCDE|\x1b[9;1H|ABCDE|'

    def aim(x):
        p = point(x, 6)
        desktop.point(p & 0xffff, p >> 16)

    # The second row is an identical, never-selected pixel reference. Give both
    # screens the same payload: preserving text alone cannot prove ownership.
    for name, alt, command, held, survives, target in (
        ('main-released', False, '?47l', False, True, False),
        ('main-pressed', False, '?1049l', True, True, False),
        ('alternate-released', True, '?1047h', False, True, True),
        ('alternate-pressed', True, '?47h', True, True, True),
        ('enter-alternate', False, '?47h', True, False, True),
        ('leave-alternate', True, '?1047l', False, False, False),
        ('erase-alternate', True, '?1049h', True, False, True),
    ):
        row = dict(case=name, command=command, held=held, survives=survives)
        rows.append(row)
        tag = 'screen-' + name
        scene = ('\x1b[?1049l\x1bc\x1b[?25l' + pattern + '\x1b[?47h' + pattern +
                 ('' if alt else '\x1b[?47l') + '\x1b[?1002;1006h')
        begin(tag+'-start', scene)
        def changes(p):
            return [x for x in range(7) if tile(p,x,6) != tile(p,x,8)]
        def clean():
            p = capture(return_pixels=True)
            return all(len(set(tile(p,x,8))) > 1 for x in range(1,6)) and not changes(p)
        wait_for(clean)
        aim(2); desktop.event(0x10,True); desktop.event(None,True)
        try:
            wait_for(lambda: desktop.state().capture == hwnd)
            if not held:
                aim(4); desktop.event(None,False); desktop.event(0x10,False)
                wait_for(lambda: desktop.state().capture != hwnd)
                wait_for(lambda: changes(capture(return_pixels=True)) == [2,3,4])
            # A repeated 1049h really clears the alternate screen. Repaint the
            # glyphs AFTER the erase so the old press has no claim on them.
            action = '\x1b[' + command + (pattern if name == 'erase-alternate' else '')
            mode = begin(tag+'-mode', action+'\x1b[?47$p\x1b[?1002$p\x1b[?1006$p', preserve_mouse=True)
            row['mode_wire'] = mode['hex']
            wanted = (b'\x1b[?47;' + (b'1' if target else b'2') + b'$y\x1b[?1002;1$y\x1b[?1006;1$y' + ack)
            begin(tag+'-end', '', preserve_mouse=True)
            if held:
                desktop.event(0x10,False); aim(4); desktop.event(None,False)
                wait_for(lambda: desktop.state().capture != hwnd)
            row['gesture_wire'] = barrier(None)
            expected = [2,3,4] if survives else []
            until = time.monotonic()+1.5
            while changes(capture(return_pixels=True)) != expected and time.monotonic()<until: time.sleep(.03)
            row['highlight'] = changes(capture(tag+'.png',return_pixels=True))
            # Right click freshly copies a live local selection, otherwise it
            # goes to the tracking child. Old clipboard contents cannot pass.
            begin(tag+'-right', '', preserve_mouse=True)
            seq = u.GetClipboardSequenceNumber(); desktop.event('right',True)
            try: wait_for(lambda: desktop.state().capture == hwnd or u.GetClipboardSequenceNumber() != seq)
            finally: desktop.event('right',False)
            wait_for(lambda: desktop.state().capture != hwnd)
            row['right_wire'] = barrier(None)
            row['copied'] = clipboard_text(hwnd) if u.GetClipboardSequenceNumber()!=seq else None
            right = b'' if survives else b'\x1b[<2;5;7M\x1b[<2;5;7m'
            row['passed'] = (row['mode_wire']==wanted.hex() and row['gesture_wire']==(ack*2).hex() and
                             row['highlight']==expected and row['copied']==('BCD' if survives else None) and
                             row['right_wire']==(ack+right+ack).hex())
        finally:
            for key in reversed(desktop.held[:]): desktop.event(key,False)
    return all(r['passed'] for r in rows)
