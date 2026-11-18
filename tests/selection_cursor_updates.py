"""Keep a physical selection through TUI cursor traffic; invalidate actual edits."""
from collections import Counter
import time
from native_test_utils import u, wait_for
from clipboard_test_utils import clipboard_text


def verify(hwnd, begin, point, capture, tile, barrier, evidence):
    # Columns 4..6 (zero based) are EFG. Cursor is hidden so its overlay
    # cannot be mistaken for a painted selection or a changed character.
    cases = [('cup-inside', 1, '{p}6H', True),
             ('tab-across', 1, '\t', True), ('cht-across', 1, '\x1b[I', True),
             ('cbt-across', 10, '\x1b[2Z', True),
             ('print-left-neighbour', 4, 'x', True),
             ('overwrite-selected', 6, 'x', False),
             ('wide-from-left', 4, '中', False),
             ('combine-on-last-selected', 8, '\u0301', False)]
    records = evidence['selection_after_cursor_traffic'] = []
    for i, (name, start_col, change, keep) in enumerate(cases):
        y = 6 if i%2 == 0 else 13
        p = f'\x1b[{y+1};'
        change = change.replace('{p}', p)
        begin('cursor-source-'+name, '\x1bc\x1b[?2027l\x1b[?25l'+p+'1HABCDEFGHIJKLM'+p+str(start_col)+'H\x1b[?1002;1006h')
        def colours(pixels):
            def colour(x):
                b=tile(pixels,x,y)
                return Counter(b[j:j+3] for j in range(0,len(b),3)).most_common(1)[0][0].hex()
            return [colour(x) for x in range(3,8)]
        def source():
            v=capture(return_pixels=True); t=tile(v,5,y)
            if len(set(t[j:j+3] for j in range(0,len(t),3)))>1 and len(set(colours(v)))==1:return colours(v)
        normal=wait_for(source)
        a,b=point(4,y),point(6,y)
        u.SendMessageW(hwnd,0x201,5,a);u.SendMessageW(hwnd,0x200,5,b);u.SendMessageW(hwnd,0x202,4,b)
        def selected():
            c=colours(capture(return_pixels=True))
            if c[1]==c[2]==c[3]!=normal[0] and c[0]==c[4]==normal[0]:return c
        marked=wait_for(selected)
        row=dict(name=name,expected_selected=keep,start_column=start_col,output_utf8=change.encode().hex(),normal=normal,marked=marked); records.append(row)
        begin('cursor-effect-'+name,change+'\x1b[?1002;1006h')
        # A repaint may follow the child acknowledgement; require repeated
        # identical screenshots before testing who owns the right click.
        def observe():return colours(capture(return_pixels=True))
        last=observe();since=time.monotonic();deadline=since+2
        while time.monotonic()<deadline:
            time.sleep(.03);v=observe()
            if v!=last:last,since=v,time.monotonic()
            if time.monotonic()-since>=.16:break
        row['after']=colours(capture('selection-cursor-'+name+'.png',return_pixels=True))
        seq=u.GetClipboardSequenceNumber();u.SendMessageW(hwnd,0x204,2,b);u.SendMessageW(hwnd,0x205,0,b)
        wire=bytes.fromhex(barrier(None));row['right_click_wire']=wire.hex()
        row['clipboard_updated']=u.GetClipboardSequenceNumber()!=seq
        row['copied']=clipboard_text(hwnd) if row['clipboard_updated'] else None
        ack=b'\x1b[0n'; raw=f'\x1b[<2;7;{y+1}M\x1b[<2;7;{y+1}m'.encode()
        row['passed']=(row['after']==(marked if keep else normal) and wire==ack+(b'' if keep else raw)+ack
                       and row['clipboard_updated']==keep and row['copied']==('EFG' if keep else None))
    assert all(r['passed'] for r in records),[r for r in records if not r['passed']]
