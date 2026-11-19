"""Follow the character under a local mouse press through terminal column edits."""
from native_test_utils import u, wait_for
from clipboard_test_utils import clipboard_text


ABC = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
# (name, edit, edit col, edit row offset, pressed x, surviving x or None,
#  released x, expected clipboard text). Coordinates are zero based. The
#  horizontal margins are columns 4..21 inclusive; vertical margins 4..16.
CASES = (
    ('ich', '\x1b[2@', 5, 0, 10, 12, 14, 'KLM'),
    ('dch', '\x1b[2P', 5, 0, 10, 8, 9, 'KL'),
    ('insert-mode', '\x1b[4h!!\x1b[4l', 5, 0, 10, 12, 14, 'KLM'),
    ('decic', "\x1b[2'}", 5, 1, 10, 12, 14, 'KLM'),
    ('decdc', "\x1b[2'~", 5, 1, 10, 8, 9, 'KL'),
    ('sl', '\x1b[2 @', 5, 1, 10, 8, 9, 'KL'),
    ('sr', '\x1b[2 A', 5, 1, 10, 12, 14, 'KLM'),
    ('other-row', '\x1b[2@', 5, 1, 10, 10, 12, 'KLM'),
    ('outside-pane', '\x1b[2P', 5, 0, 2, 2, 3, 'CD'),
    ('wide-tail', '\x1b[2@', 4, 0, 7, 9, 10, '中q\u0301'),
    ('bidi-stays', '\x1b[2P', 10, 0, 11, 9, 10, 'אR'),
    ('lost-at-right', '\x1b[2@', 5, 0, 20, None, 18, None),
    ('deleted', '\x1b[2P', 5, 0, 6, None, 8, None),
    ('cut-wide-head', '\x1b[2P', 7, 0, 6, None, 9, None),
    ('cut-wide-tail', "\x1b[2'~", 7, 1, 7, None, 10, None),
    ('paint-replaced', 'Z', 10, 0, 10, None, 12, None),
    ('paint-neighbour', '!', 11, 0, 10, 10, 12, 'K!M'),
    ('paint-identical', 'K', 10, 0, 10, 10, 12, 'KLM'),
    ('paint-wide-trailer', '!', 7, 0, 6, None, 9, None),
    ('paint-widen', '中', 9, 0, 10, None, 13, None),
    ('paint-combine', '\u0301', 11, 0, 10, None, 13, None),
    ('bidi-repaint', 'XY', 10, 0, 11, 9, 10, 'אX'),
    # Repaint an identical base to establish a live cluster. The following
    # scalar changes the held text or consumes its neighbour after widening.
    ('cluster-append', '\x1b[?2027hK\u0301', 10, 0, 10, None, 13, None),
    ('cluster-widen', '\x1b[?2027h❤\ufe0f', 10, 0, 11, None, 13, None),
    ('cluster-wrap', '\x1b[?2027h❤\ufe0f', 21, -1, 4, None, 8, None),
    ('cluster-wrap-neighbour', '\x1b[?2027h❤\ufe0f', 21, -1, 6, 6, 8, 'GHI'),
    ('cluster-insert', '\x1b[?2027h\x1b[4h❤\ufe0f\x1b[4l', 10, 0, 10, 12, 14, 'KLM'),
    ('paint-back', 'Z\bK', 10, 0, 10, None, 12, None),
)
ACK = b'\x1b[0n'


def verify(hwnd, begin, point, capture, tile, copy, barrier, evidence, desktop=None, await_input=None):
    rows = evidence['horizontal_press_system' if desktop else 'horizontal_press'] = []
    def aim(cell): desktop.point(cell & 0xffff, cell >> 16)
    for i, (name, edit, col, dy, press, dest, end, want) in enumerate(CASES):
        if desktop and name not in ('ich','dch','deleted','paint-replaced','paint-identical'): continue
        block = bool(i % 2)
        y = 8 if i % 2 == 0 else 13  # distinguish consecutive independent Win32 clicks
        phase = ('physical-' if desktop else 'message-')+'column-'+name
        line = ('ABCDEF中q\u0301JKLMNOPQRSTUVWXYZ' if name in ('wide-tail','cut-wide-head','cut-wide-tail','paint-wide-trailer') else
                'ABCDEFGHLאבג\u05b0RSTUVWXYZ' if name in ('bidi-stays','bidi-repaint') else ABC)
        row = dict(case=name, block=block, pressed=[press,y], released=[end,y],
                   destination=dest, expected=want, passed=False);rows.append(row)
        begin(phase+'-draw', f'\x1bc\x1b[?25l\x1b[{y+1};1H'+line+
              '\x1b[22;51HAB\x1b[?69h\x1b[5;22s\x1b[5;17r\x1b[?1002;1006h')
        def ready():
            p=capture(return_pixels=True)
            return p if tile(p,50,21)!=tile(p,51,21) and tile(p,51,21)!=tile(p,52,21) else None
        initial=wait_for(ready)
        if desktop:
            aim(point(press,y));desktop.event(0x10,True)
            if block:desktop.event(0x11,True)
            desktop.event(None,True);wait_for(lambda:desktop.state().capture==hwnd)
        else:u.SendMessageW(hwnd,0x201,13 if block else 5,point(press,y))
        try:
            begin(phase+'-scroll',f'\x1b[{y+dy+1};{col+1}H'+edit+'\x1b[22;51HB')
            def repainted():
                p=capture(return_pixels=True)
                return p if tile(p,50,21)==tile(initial,51,21) else None
            normal=wait_for(repainted)
            if dest is not None:
                row['same_glyph_pixels']=tile(initial,press,y)==tile(normal,dest,y)
            if desktop:
                if block:desktop.event(0x11,False)
                desktop.event(0x10,False);aim(point(end,y))
            elif i%3: u.SendMessageW(hwnd,0x200,1,point(end,y))
        finally:
            if desktop:
                desktop.event(None,False);wait_for(lambda:desktop.state().capture!=hwnd)
            else:u.SendMessageW(hwnd,0x202,0,point(end,y))
        row['gesture_wire']=barrier(None)
        # Right click is also a safe observation of 'no selection': with mouse
        # tracking active it must go to the child and leave the clipboard alone.
        begin(phase+'-right','');seq=u.GetClipboardSequenceNumber()
        if desktop:
            desktop.event('right',True)
            try:wait_for(lambda:desktop.state().capture==hwnd or seq!=u.GetClipboardSequenceNumber())
            finally:desktop.event('right',False)
        else:u.SendMessageW(hwnd,0x204,2,point(end,y));u.SendMessageW(hwnd,0x205,0,point(end,y))
        if desktop:
            wait_for(lambda:desktop.state().capture!=hwnd)
            if seq==u.GetClipboardSequenceNumber():await_input()
        row['right_wire']=barrier(None)
        changed=(seq!=u.GetClipboardSequenceNumber());row['clipboard_changed']=changed
        row['right_copy']=clipboard_text(hwnd) if changed else None
        # Skip the Copy timeout when the original image fails to select anything.
        row['shortcut_copy']=copy() if changed and want is not None else None
        after=capture(phase+'.png',return_pixels=True)
        row['highlight']=[x for x in range(28) if tile(after,x,y)!=tile(normal,x,y)]
        wanted=(list(range(min(dest,end),max(dest,end)+1)) if dest is not None else [])
        if name=='wide-tail':wanted.insert(0,dest-1)
        row['expected_highlight']=wanted
        wire=ACK if want is not None else ACK+f'\x1b[<2;{end+1};{y+1}M\x1b[<2;{end+1};{y+1}m'.encode()
        row['passed']=(row['gesture_wire']==(2*ACK).hex() and row['right_wire']==(wire+ACK).hex()
                       and changed==(want is not None) and row['right_copy']==row['shortcut_copy']==want
                       and row.get('same_glyph_pixels',True) and row['highlight']==wanted)
    return all(row['passed'] for row in rows)
