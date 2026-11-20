"""Follow the character under a local mouse press through terminal column edits."""
from native_test_utils import os, root, u, wait_for
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
    # A full-screen application can erase a cell before the user releases
    # the mouse. A protected character or an untouched neighbour stays usable.
    ('erase-ech', '\x1b[X', 10, 0, 10, None, 12, None),
    ('erase-ech-neighbour', '\x1b[X', 11, 0, 10, 10, 12, 'K M'),
    ('erase-el', '\x1b[K', 10, 0, 10, None, 8, None),
    ('erase-ed', '\x1b[J', 10, 0, 10, None, 8, None),
    ('erase-rect', '\x1b[{row};11;{row};12$z', 0, 0, 10, None, 12, None),
    ('erase-selective', '\x1b[?1K', 10, 0, 10, None, 12, None),
    ('erase-protected', '\x1b[?1K', 10, 0, 10, 10, 12, 'KLM'),
    ('erase-selective-rect', '\x1b[{row};11;{row};12${', 0, 0, 10, None, 12, None),
    ('erase-protected-rect', '\x1b[{row};11;{row};12${', 0, 0, 10, 10, 12, 'K M'),
    ('erase-wide-trailer', '\x1b[X', 7, 0, 6, None, 9, None),
    ('erase-blank', '\x1b[3X', 9, 0, 10, 10, 12, '  M'),
    ('erase-other-row', '\x1b[2K', 10, -1, 10, 10, 12, 'KLM'),
    # The old continuation at the vacated margin must not erase the new V
    # or the second half of 界. Keep the press held while the cells move.
    ('edge-dch', '\x1b[2P', 5, 0, 21, 19, 17, '中V'),
    ('edge-decdc', "\x1b[2'~", 5, 1, 21, 19, 17, '中V'),
    ('edge-sl', '\x1b[2 @', 5, 1, 21, 19, 17, '中V'),
    ('edge-adjacent-wide', '\x1b[3P', 5, 0, 21, 18, 15, '中界'),
    ('edge-right-ich', '\x1b[@', 5, 0, 20, 21, 19, '中U'),
    ('edge-right-sr', '\x1b[1 A', 5, 1, 20, 21, 19, '中U'),
    # Rectangle writes redraw without moving the cursor. Track the original
    # text (including a wide tail or combining mark), not the painted cell.
    ('fill-replaced', '\x1b[90;{row};10;{row};12$x', 0, 0, 10, None, 12, None),
    ('fill-identical', '\x1b[75;{row};11;{row};11$x', 0, 0, 10, 10, 12, 'KLM'),
    ('fill-neighbour', '\x1b[90;{row};12;{row};12$x', 0, 0, 10, 10, 12, 'KZM'),
    ('fill-wide-tail', '\x1b[90;{row};8;{row};8$x', 0, 0, 6, None, 9, None),
    ('fill-strips-accent', '\x1b[75;{row};11;{row};11$x', 0, 0, 10, None, 12, None),
    ('fill-bidi-neighbour', '\x1b[88;{row};11;{row};12$x', 0, 0, 11, 9, 10, 'אX'),
    ('copy-replaced', '\x1b[{row};1;{row};3;1;{row};11;1$v', 0, 0, 10, None, 12, None),
    ('copy-from-press', '\x1b[{row};11;{row};13;1;{row};15;1$v', 0, 0, 10, 10, 12, 'KLM'),
    ('copy-overlap', '\x1b[{row};9;{row};12;1;{row};10;1$v', 0, 0, 10, None, 12, None),
    ('copy-wide-tail', '\x1b[{row};1;{row};1;1;{row};8;1$v', 0, 0, 6, None, 9, None),
    ('copy-same-accent', '\x1b[{row};5;{row};5;1;{row};11;1$v', 0, 0, 10, 10, 12, 'K\u0301LM'),
    ('copy-new-accent', '\x1b[{row};5;{row};5;1;{row};11;1$v', 0, 0, 10, None, 12, None),
    ('repeat-cell-stream', '\x1b[2@', 5, 0, 10, 12, 14, 'KLM'),
    ('repeat-cell-block', '\x1b[2@', 5, 0, 10, 12, 14, 'KLM'),
)
ACK = b'\x1b[0n'


def verify(hwnd, begin, point, capture, tile, copy, barrier, evidence, desktop=None, await_input=None):
    rows = evidence['horizontal_press_system' if desktop else 'horizontal_press'] = []
    def aim(cell): desktop.point(cell & 0xffff, cell >> 16)
    for i, (name, edit, col, dy, press, dest, end, want) in enumerate(CASES):
        if desktop and name not in ('ich','dch','deleted','paint-replaced','paint-identical','erase-ech','erase-protected','edge-dch','edge-adjacent-wide','edge-right-ich','edge-right-sr','fill-replaced','fill-identical',
                                   'copy-overlap','copy-same-accent'): continue
        block = bool(i % 2)
        y = 8 if i % 2 == 0 else 13  # distinguish consecutive independent Win32 clicks
        phase = ('physical-' if desktop else 'message-')+'column-'+name
        line = ('ABCDEF中q\u0301JKLMNOPQRSTUVWXYZ' if name in ('wide-tail','cut-wide-head','cut-wide-tail','paint-wide-trailer','erase-wide-trailer',
                                                                    'fill-wide-tail','copy-wide-tail') else
                'ABCDEFGHLאבג\u05b0RSTUVWXYZ' if name in ('bidi-stays','bidi-repaint','fill-bidi-neighbour') else ABC)
        if name in ('fill-strips-accent','copy-same-accent','copy-new-accent'):
            line=line.replace('K','K\u0301').replace('E','K\u0300' if name=='copy-new-accent' else 'K\u0301')
        if name.startswith('edge-'):
            line = 'ABCDEFGHIJKLMNOPQR中界WXYZ' if name=='edge-adjacent-wide' else 'ABCDEFGHIJKLMNOPQRS中VWXYZ'
            if name.startswith('edge-right-'): line = 'ABCDEFGHIJKLMNOPQR中UVWXYZ'
        if name in ('erase-protected','erase-protected-rect'):
            line=line.replace('K','\x1b[1"qK\x1b[0"q')
        if name=='erase-blank': line=line.replace('K',' ')
        edit=edit.replace('{row}',str(y+1))
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
            if name.startswith('repeat-cell-'):
                # The character moved two cells; the pointer did not. Deliver a
                # client mouse-move at exactly the original down coordinates.
                at=point(press,y);row['down_and_motion_lparam']=at
                u.SendMessageW(hwnd,0x200,13 if block else 5,at)
                # While the button is still held the terminal must service a
                # DSR and leak no SGR mouse report. Restart a fresh interval
                # afterwards so the ordinary drag's wire oracle is unchanged.
                row['wire_before_real_drag']=barrier()
                begin(phase+'-resume','')
            if dest is not None:
                row['same_glyph_pixels']=tile(initial,press,y)==tile(normal,dest,y)
            if name.startswith('edge-'):
                shift=press-dest
                # Compare the whole painted span, the vacated cells and the W
                # outside the right margin, independently of clipboard text.
                def strip(frame, start, stop):
                    return b''.join(tile(frame,x,y) for x in range(start,stop))
                blank=tile(initial,27,y)
                row['moved_span_visible']=(strip(normal,end,dest+1)==strip(initial,end+shift,dest+1+shift)
                                           and strip(normal,end,dest+1)!=blank*(dest-end+1))
                gap = 22-shift if shift>0 else (4 if name=='edge-right-sr' else col)
                row['vacated_blank']=strip(normal,gap,gap+abs(shift))==blank*abs(shift)
                row['outside_preserved']=tile(initial,22,y)==tile(normal,22,y)!=blank
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
        if name.startswith('repeat-cell-') and os.environ.get('NEMOTERM_STATIONARY_FRAMES')=='1':
            # Preserve the buffers already used by the assertions. Capturing a
            # second time could sample a different repaint or delay the gesture.
            from PIL import Image
            with Image.open(root/'research'/(phase+'.png')) as image:
                size=image.size
            for stage,pixels in [('source',initial),('edited',normal)]:
                assert len(pixels)==3*size[0]*size[1]
                Image.frombytes('RGB',size,pixels).save(root/'research'/(phase+'-'+stage+'.png'))
        row['highlight']=[x for x in range(28) if tile(after,x,y)!=tile(normal,x,y)]
        wanted=(list(range(min(dest,end),max(dest,end)+1)) if dest is not None else [])
        if name=='wide-tail':wanted.insert(0,dest-1)
        row['expected_highlight']=wanted
        wire=ACK if want is not None else ACK+f'\x1b[<2;{end+1};{y+1}M\x1b[<2;{end+1};{y+1}m'.encode()
        row['passed']=(row['gesture_wire']==(2*ACK).hex() and row['right_wire']==(wire+ACK).hex()
                       and changed==(want is not None) and row['right_copy']==row['shortcut_copy']==want
                       and row.get('same_glyph_pixels',True) and row['highlight']==wanted
                       and all(row.get(k,True) for k in ('moved_span_visible','vacated_blank','outside_preserved')))
    return all(row['passed'] for row in rows)
