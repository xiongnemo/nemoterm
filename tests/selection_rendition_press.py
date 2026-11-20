"""Keep a held Shift press on its glyph when the application changes a row's width."""
from native_test_utils import u, wait_for
from clipboard_test_utils import clipboard_text


# Initial and final line rendition, command, rectangular modifier, physical click
# and release columns, expected final highlighted columns. Rows start at zero.
CASES = (
    ('widen-block', '5','6','\x1b#6',True,4,13,'EFG',range(8,14)),
    ('narrow-block','6','5','\x1b#5',True,9,6,'EFG',range(4,7)),
    ('hidden-stream','5','6','\x1b#6',False,42,13,None,()),
    ('widen-stream','5','6','\x1b#6',False,4,13,'EFG',range(8,14)),
    ('same-scale','6','4','\x1b#4',True,9,13,'EFG',range(8,14)),
    ('enable-margins','6','5','\x1b[?69h',True,9,6,'EFG',range(4,7)),
    ('other-row','5','5',None,True,4,6,'EFG',range(4,7)),
)
ACK = b'\x1b[0n'


def verify(hwnd, begin, point, capture, tile, copy, barrier, evidence, desktop=None):
    records = evidence['resize_press_system' if desktop else 'resize_press_messages'] = []
    text = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    def aim(p): desktop.point(p & 65535,p >> 16)
    for i,(name,old,new,command,block,press,end,want,columns) in enumerate(CASES):
        if desktop and name not in ('widen-block','hidden-stream','enable-margins'):continue
        y = 5 if i%2==0 else 11
        tag = ('system-' if desktop else '')+'resize-press-'+name
        cup = lambda row: f'\x1b[{row+1};1H'
        # Populate in single width, then set rendition. The rows at +3/+5
        # independently show what the target should look like before/after.
        scene = '\x1bc\x1b[?25l'
        for dy,size in [(0,old),(3,old),(5,new)]:scene+=cup(y+dy)+text+cup(y+dy)+'\x1b#'+size
        begin(tag+'-start',scene+'\x1b[?1002;1006h')
        def matching(ref):
            p=capture(return_pixels=True)
            if tile(p,0,y)==tile(p,1,y+1):return None
            return p if all(tile(p,x,y)==tile(p,x,ref) for x in range(80)) else None
        wait_for(lambda:matching(y+3)); p,q=point(press,y),point(end,y)
        if desktop:
            aim(p);desktop.event(0x10,True)
            if block:desktop.event(0x11,True)
            desktop.event(None,True);wait_for(lambda:desktop.state().capture==hwnd)
        else:u.SendMessageW(hwnd,0x201,13 if block else 5,p)
        try:
            # tracked_phase verifies that both tracking modes are still enabled
            # before the mouse moves; do not let the child reset them mid-gesture.
            begin(tag+'-scroll',cup(y if command else y+1)+(command or '\x1b#6'))
            before=wait_for(lambda:matching(y+5));capture(tag+'-before-release.png')
            if desktop:
                if block:desktop.event(0x11,False)
                desktop.event(0x10,False);aim(q)
            else:u.SendMessageW(hwnd,0x200,1,q)
        finally:
            if desktop:
                for key in reversed(desktop.held[:]):desktop.event(key,False)
                wait_for(lambda:desktop.state().capture!=hwnd)
            else:u.SendMessageW(hwnd,0x202,0,q)
        gesture=barrier(None);begin(tag+'-right','');seq=u.GetClipboardSequenceNumber()
        if desktop:
            desktop.event('right',True)
            try:wait_for(lambda:desktop.state().capture==hwnd or u.GetClipboardSequenceNumber()!=seq)
            finally:desktop.event('right',False)
            wait_for(lambda:desktop.state().capture!=hwnd)
        else:u.SendMessageW(hwnd,0x204,2,q);u.SendMessageW(hwnd,0x205,0,q)
        wire=barrier(None);changed=u.GetClipboardSequenceNumber()!=seq
        right=clipboard_text(hwnd) if changed else None
        shortcut=copy() if changed and want is not None else None
        after=capture(tag+'-after-release.png',return_pixels=True)
        highlight=[x for x in range(80) if tile(before,x,y)!=tile(after,x,y)]
        raw=b'' if want else f'\x1b[<2;{end+1};{y+1}M\x1b[<2;{end+1};{y+1}m'.encode()
        records.append(dict(case=name,gesture=gesture,right_wire=wire,clipboard_changed=changed,
            right_copy=right,shortcut_copy=shortcut,expected_copy=want,highlight=highlight,expected_highlight=list(columns),
            passed=(gesture==(ACK*2).hex() and wire==(ACK+raw+ACK).hex() and changed==(want is not None)
                    and right==shortcut==want and highlight==list(columns))))
    return all(r['passed'] for r in records)
