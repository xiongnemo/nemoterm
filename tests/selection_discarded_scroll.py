"""A press on a glyph that scrolls away must not select its replacement."""
from native_test_utils import u, wait_for
from clipboard_test_utils import clipboard_text


def verify(hwnd, begin, point, capture, tile, copy, barrier, evidence):
    cases = evidence['discarded_scroll_press'] = []
    # 0-based columns 8..21, rows 6..13. Exercise either half of a wide
    # glyph at BOTH pane edges as well as rows lost with/without LR margins.
    for n, (name, down, split, wide, x, y) in enumerate((
        ('pane-top', False, True, None, 12, 6), ('pane-bottom', True, True, None, 13, 13),
        ('row-top', False, False, None, 12, 6), ('row-bottom', True, False, None, 13, 13),
        ('left-lead', True, True, 7, 7, 9), ('left-tail', False, True, 7, 8, 9),
        ('right-lead', False, True, 21, 21, 9), ('right-tail', True, True, 21, 22, 9),
    )):
        row = dict(case=name, press=[x,y], block=bool(n%2), drag=bool((n//2)%2)); cases.append(row)
        margins = '\x1b[?69h\x1b[9;22s' if split else ''
        src = '\x1bc\x1b[?25l'
        for a in range(6,14): src += f'\x1b[{a+1};1H' + chr(65+a)*32
        if wide is not None: src += f'\x1b[{y+1};{wide+1}H中'
        begin(name+'-source',src+'\x1b[21;3HSAFE'+margins+'\x1b[7;14r\x1b[?1002;1006h')
        def ink(p,x,y):
            cell=tile(p,x,y);return len(set(cell[i:i+3] for i in range(0,len(cell),3)))>1
        def drawn():
            p=capture(return_pixels=True)
            return p if ink(p,3,20) and ink(p,12,6) and not ink(p,51,20) else None
        original=wait_for(drawn);u.SendMessageW(hwnd,0x201,13 if row['block'] else 5,point(x,y))
        end=point(x+3,y)
        try:
            begin(name+'-scroll','\x1b[1'+('T' if down else 'S')+'\x1b[21;52H!')
            def scrolled():
                p=capture(return_pixels=True)
                cells=(wide,wide+1) if wide is not None else (x,)
                return p if ink(p,51,20) and any(tile(p,i,y)!=tile(original,i,y) for i in cells) else None
            normal=wait_for(scrolled);capture('discard-'+name+'-scrolled.png')
            if row['drag']:u.SendMessageW(hwnd,0x200,1,end)
        finally:u.SendMessageW(hwnd,0x202,0,end)
        row['gesture_wire']=barrier(None)
        # With no selection, the next right click must reach the application.
        # A false highlight would instead intercept it and overwrite the clipboard.
        begin(name+'-right','');seq=u.GetClipboardSequenceNumber()
        u.SendMessageW(hwnd,0x204,2,end);u.SendMessageW(hwnd,0x205,0,end)
        row['right_wire']=barrier(None);row['clipboard_changed']=seq!=u.GetClipboardSequenceNumber()
        row['copied']=clipboard_text(hwnd) if row['clipboard_changed'] else None
        after=capture('discard-'+name+'-released.png',return_pixels=True)
        row['changed']=[[i,a] for a in range(6,14) for i in range(33) if tile(after,i,a)!=tile(normal,i,a)]
        # No reset or focus change between the discarded gesture and a new one.
        begin(name+'-recover','');u.SendMessageW(hwnd,0x201,5,point(2,20));u.SendMessageW(hwnd,0x202,0,point(5,20))
        row['next_copy']=copy();row['next_wire']=barrier(None)
        ack=b'\x1b[0n';raw=f'\x1b[<2;{x+4};{y+1}M\x1b[<2;{x+4};{y+1}m'.encode()
        row['passed']=(row['changed']==[] and not row['clipboard_changed'] and row['right_wire']==(ack+raw+ack).hex()
                       and row['gesture_wire']==row['next_wire']==(ack*2).hex() and row['next_copy']=='SAFE')
    return all(r['passed'] for r in cases)
