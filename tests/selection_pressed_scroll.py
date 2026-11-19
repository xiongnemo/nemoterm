"""A TUI can scroll a pressed glyph before Windows delivers the first drag."""
from native_test_utils import u, wait_for


def verify(hwnd,begin,point,capture,tile,copy,barrier,evidence):
    rows=evidence['pressed_scroll_anchor']=[]
    for direction,seq in ((1,'T'),(-1,'S')):
        for block in (False,True):
            base='anchor-'+('down' if direction==1 else 'up')+('-block' if block else '-stream')
            y=8; target=y+direction; expected='A中e\u0301'
            begin(base+'-source','\x1bc\x1b[?25l\x1b[5;17r\x1b[8;1Habove|\x1b[9;1H#A中e\u0301Z|\x1b[10;1Hbelow|\x1b[?1002;1006h')
            def source():
                p=capture(return_pixels=True);t=tile(p,1,y)
                return p if len(set(t[n:n+3] for n in range(0,len(t),3)))>1 and tile(p,1,target)!=t else None
            before=wait_for(source)
            row=dict(case=base,pressed=[1,y],released=[4,target],expected=expected);rows.append(row)
            u.SendMessageW(hwnd,0x201,13 if block else 5,point(1,y))
            try:
                # DSR acknowledges the real scroll while pressed. No move event
                # yet: once a drag starts, the terminal intentionally holds output.
                begin(base+'-scroll','\x1b[1'+seq)
                def moved():
                    p=capture(return_pixels=True)
                    return p if all(tile(p,x,target)==tile(before,x,y) for x in range(7)) else None
                moved_frame=wait_for(moved);row['source_row_moved']=True
                u.SendMessageW(hwnd,0x200,1,point(4,target))
            finally:u.SendMessageW(hwnd,0x202,0,point(4,target))
            row['copied']=copy();row['wire']=barrier()
            def painted():
                p=capture(return_pixels=True)
                return [[x for x in range(8) if tile(p,x,i)!=tile(moved_frame,x,i)] for i in sorted((target,y))]
            want=[[1,2,3,4] if i==target else [] for i in sorted((target,y))]
            try:wait_for(lambda:painted()==want,timeout=1)
            except AssertionError:pass
            row['highlighted']=painted();row['expected_highlight']=want
            capture('selection-'+base+'.png');row['passed']=row['copied']==expected and row['highlighted']==want
    assert all(r['passed'] for r in rows),rows
