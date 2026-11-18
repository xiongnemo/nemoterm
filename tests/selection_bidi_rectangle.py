"""A physical block can select disjoint source spans in one bidirectional row."""
from collections import Counter
from native_test_utils import u, time, wait_for
from clipboard_test_utils import clipboard_text


def verify(hwnd, begin, point, capture, tile, shortcut, barrier, evidence, *, block=True):
    # Unique backgrounds let the native surface itself identify each glyph.
    # Logical source A, alef, bet, gimel+sheva, Z; LTR paragraph paints
    # A, gimel+sheva, bet, alef, Z. Clipboard retains source spelling/order.
    letters=('A','\u05d0','\u05d1','\u05d2\u05b0','Z')
    palette=('42;72;100','80;45;71','43;86;49','101;54;41','61;43;102')
    def coloured(tokens):return ''.join('\x1b[48;2;'+rgb+'m'+ch for rgb,ch in zip(palette,tokens))+'\x1b[0m'
    cases=[('through-middle',(0,0),(1,2),False,'01\r\nA'+letters[3]+'\r\nab',[[0,1],[0,1],[0,1]]),
           ('reverse-through-run',(2,1),(1,1),False,letters[2]+letters[3],[[],[1,2],[]]),
           ('through-right-edge',(4,1),(3,0),False,'34\r\n'+letters[1]+'Z',[[3,4],[3,4],[]]),
           ('doubled-middle',(3,0),(5,2),True,'345\r\n'+letters[2]+letters[3]+'\r\ndef',[[3,4,5],[2,3,4,5],[3,4,5]])]
    if not block:
        cells_to_edge=list(range(8,14)) # observed crop extends to column 13
        cases=[('linear-left',(0,1),(1,1),False,'A'+letters[3],[[],[0,1],[]]),
               ('linear-reverse-right',(4,1),(3,1),False,letters[1]+'Z',[[],[3,4],[]]),
               ('linear-two-rows',(8,0),(1,1),False,'89\r\nA'+letters[3],[cells_to_edge,[0,1],[]]),
               ('linear-reverse-doubled',(2,1),(8,0),True,'89\r\nA'+letters[3],[cells_to_edge,[0,1,2,3],[]]),
               ('linear-whole-middle',(8,0),(1,2),False,'89\r\n'+''.join(letters)+'\r\nab',[cells_to_edge,list(range(14)),[0,1]])]
    records=evidence['bidi_rectangles' if block else 'bidi_streams']=[]
    for i,(name,start,end,doubled,expected,cells) in enumerate(cases):
        top=3 if i%2==0 else 12
        seq=(f'\x1bc\x1b[?25l\x1b[{top+1};1H0123456789\x1b[{top+2};1H'+('\x1b#6' if doubled else '')+
             coloured(letters)+f'\x1b[{top+3};1Habcdefghij\x1b[{top+4};1H'+coloured('     ')+'\x1b[?1002;1006h')
        begin('bidi-'+name,seq)
        row=dict(case=name,expected=expected,expected_columns=cells);records.append(row)
        def background(pic,x,y):
            b=tile(pic,x,y);return Counter(b[n:n+3] for n in range(0,len(b),3)).most_common(1)[0][0]
        def visible():
            p=capture(return_pixels=True);key=[background(p,x,top+3) for x in range(5)]
            if len(set(key))!=5:return None
            line=[background(p,x,top+1) for x in range(5*(1+int(doubled)))];visual=[key.index(v) if v in key else -1 for v in line]
            row['visual_source_indices']=visual
            return p if visual==[x for x in (0,3,2,1,4) for _ in range(1+int(doubled))] else None
        try:before=wait_for(visible)
        finally:capture('selection-bidi-'+name+'-before.png')
        def coord(pt):return point(pt[0],top+pt[1])
        u.SendMessageW(hwnd,0x201,13 if block else 5,coord(start));u.SendMessageW(hwnd,0x200,1,coord(end));u.SendMessageW(hwnd,0x202,0,coord(end))
        row['child_hex']=barrier()
        def changed(p):return [[x for x in range(14) if tile(before,x,top+y)!=tile(p,x,top+y)] for y in range(3)]
        until=time.monotonic()+2
        while changed(capture(return_pixels=True))!=cells and time.monotonic()<until:time.sleep(.04)
        row['columns']=changed(capture('selection-bidi-'+name+'-after.png',return_pixels=True))
        seqnum=u.GetClipboardSequenceNumber();shortcut(67,46)
        row['copied']=clipboard_text(hwnd) if u.GetClipboardSequenceNumber()!=seqnum else None
        row['passed']=row['copied']==expected and row['columns']==cells
    assert all(r['passed'] for r in records),records
