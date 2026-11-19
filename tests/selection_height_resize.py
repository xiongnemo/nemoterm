"""A height-only native window resize during or after a real Shift selection."""
from native_test_utils import c, w, u, wait_for, time
from clipboard_test_utils import clipboard_text


def verify(host, hwnd, begin, point, capture, tile, barrier, desktop, evidence):
    records = evidence['height_selection'] = []
    ack = b'\x1b[0n'
    ch = evidence['cell_pixels'][1]

    def size(target, client):
        r = w.RECT()
        assert (u.GetClientRect if client else u.GetWindowRect)(target, c.byref(r))
        return [r.right-r.left, r.bottom-r.top]

    outer, client = size(host, False), size(hwnd, True)
    def height(delta):
        assert desktop.u.SetWindowPos(host, None, 0, 0, outer[0], outer[1]+delta*ch, 0x16)
        expected = [client[0], client[1]+delta*ch]
        wait_for(lambda: size(hwnd, True) == expected)
        return expected

    def aim(x, y):
        p = point(x,y); desktop.point(p & 0xffff, p >> 16)

    # Each source row has matching glyphs on the resized row. The two
    # neighboring unselected cells make a row shift or blanket repaint visible.
    for name, alt, block, held, delta, shift in (
        ('main-retained', False, False, False, -2, 0),
        ('main-to-history', False, False, False, -2, -2),
        ('alternate-block', True, True, True, 1, 0),
        ('alternate-lost', True, False, True, -2, 0),
    ):
        dropped = name == 'alternate-lost'
        top = 22 if dropped else 6
        newtop = 6 if dropped else top+shift
        row = dict(case=name, before=client, expected_text=None if dropped else ('BCD\r\nbcd' if block else 'BCD'))
        records.append(row)
        scene = '\x1b[?1049l\x1bc\x1b[3J' + ('\x1b[?1049h' if alt else '') + '\x1b[?25l'
        scene += '\x1b[7;1H|ABCDE|\r\n|abcde|'
        if dropped: scene += '\x1b[23;1H|ABCDE|'
        scene += ('\x1b[24;1H' if shift else '\x1b[1;1H') + '\x1b[?1002;1006h'
        begin('height-'+name, scene)
        def drawn():
            p = capture(return_pixels=True)
            return p if all(len(set(tile(p,x,y)))>1 for y in (6,top) for x in (1,2,4,5)) else None
        before = wait_for(drawn)
        aim(2,top); desktop.event(0x10,True)
        if block: desktop.event(0x11,True)
        desktop.event(None,True); wait_for(lambda: desktop.state().capture==hwnd)
        try:
            if not held:
                aim(4,top); desktop.event(None,False); desktop.event(0x10,False)
                wait_for(lambda: desktop.state().capture!=hwnd)
                wait_for(lambda: tile(capture(return_pixels=True),3,top)!=tile(before,3,top))
            row['resized'] = height(delta)
            if held:
                if block: desktop.event(0x11,False)
                desktop.event(0x10,False); aim(4,newtop+int(block)); desktop.event(None,False)
                wait_for(lambda: desktop.state().capture!=hwnd)
            row['gesture_wire'] = barrier(None)
            expected = [] if dropped else [[x,y] for y in range(1+int(block)) for x in (2,3,4)]
            def changes(p):
                return [[x,y] for y in range(1+int(block)) for x in range(7)
                        if tile(p,x,newtop+y)!=tile(before,x,6+y)]
            until=time.monotonic()+1.5
            while changes(capture(return_pixels=True))!=expected and time.monotonic()<until: time.sleep(.03)
            row['highlight'] = changes(capture('height-'+name+'.png',return_pixels=True))
            row['expected_highlight'] = expected
            if not dropped:
                begin('height-copy-'+name,'',preserve_mouse=True)
                seq=u.GetClipboardSequenceNumber(); desktop.chord(0x11,0x10,ord('C'))
                row['copy_wire']=barrier(None)
                row['copied']=clipboard_text(hwnd) if u.GetClipboardSequenceNumber()!=seq else None
            begin('height-right-'+name,'',preserve_mouse=True)
            aim(4,newtop+int(block));seq=u.GetClipboardSequenceNumber();desktop.event('right',True)
            try:wait_for(lambda: desktop.state().capture==hwnd or u.GetClipboardSequenceNumber()!=seq)
            finally:desktop.event('right',False)
            wait_for(lambda: desktop.state().capture!=hwnd)
            row['right_wire']=barrier(None)
            row['right_copy']=clipboard_text(hwnd) if u.GetClipboardSequenceNumber()!=seq else None
            wire=f'\x1b[<2;5;{newtop+1}M\x1b[<2;5;{newtop+1}m'.encode() if dropped else b''
            row['passed']=(row['gesture_wire']==(ack*2).hex() and row['highlight']==expected and
                           row.get('copied')==row['expected_text']==row['right_copy'] and
                           (dropped or row['copy_wire']==(ack*2).hex()) and row['right_wire']==(ack+wire+ack).hex())
        finally:
            for key in reversed(desktop.held[:]): desktop.event(key,False)
            height(0)
    return all(r['passed'] for r in records)
