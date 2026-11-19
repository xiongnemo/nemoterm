"""Compare word selection with glyph positions actually painted by the frontend."""
from collections import Counter
from native_test_utils import u, wait_for, time


def verify(hwnd, begin, point, capture, tile, copy, barrier, evidence, desktop=None):
    tokens = ('A', '\u05d0', '!', '\u05d1\u05b0', 'Z')
    rgb = ('42;72;100','80;45;71','43;86;49','101;54;41','61;43;102')
    def draw(chars):
        return ''.join('\x1b[48;2;'+colour+'m'+ch for colour,ch in zip(rgb,chars))+'\x1b[0m'
    def bg(pic,x,y):
        pixels=tile(pic,x,y)
        return Counter(pixels[i:i+3] for i in range(0,len(pixels),3)).most_common(1)[0][0]
    cases = [ # click position is a physical column, even in a double-width row
        ('visual-left',0,1,2,False,True,'A'+tokens[3],[0,1]),
        ('visual-right',4,1,2,False,True,tokens[1]+'Z',[3,4]),
        ('punctuation',2,1,2,False,True,'!',[2]),
        ('double-width',3,2,2,False,True,'A'+tokens[3],[0,1,2,3]),
        ('soft-wrap',0,1,2,True,True,'QA'+tokens[3],[0,1]),
        ('line',3,1,3,False,True,''.join(tokens)+'\r\n',list(range(80))),
        ('ordinary-word',0,1,2,False,False,'A'+tokens[1],[0,3]),
    ]
    rows=evidence['bidi_word_system' if desktop else 'bidi_word_messages']=[]
    for i,(name,x,scale,count,wrapped,shift,expected,columns) in enumerate(cases):
        if desktop and name not in ('visual-left','visual-right','punctuation'):continue
        y=(7,15)[i%2];phase=('system-' if desktop else 'message-')+'bidi-word-'+name
        start=(f'\x1b[{y};1H'+'.'*79+'Q' if wrapped else f'\x1b[{y+1};1H')
        begin(phase, '\x1bc\x1b[?25l\x1b[?7h'+start+('\x1b#6' if scale==2 else '')+draw(tokens)+
              f'\x1b[{y+3};1H'+draw('     ')+('\x1b[?1002;1006h' if shift else ''))
        row=dict(case=name, expected=expected, expected_highlight=columns, passed=False);rows.append(row)
        def ready():
            p=capture(return_pixels=True);key=[bg(p,col,y+2) for col in range(5)]
            if len(set(key))!=5:return None
            raw=[bg(p,col,y) for col in range(5*scale)];indices=[key.index(v) if v in key else -1 for v in raw]
            row['visible_source_indices']=indices
            return p if indices==[v for v in (0,3,2,1,4) for _ in range(scale)] else None
        before=wait_for(ready);capture(phase+'-source.png');p=point(x,y)
        if desktop:
            desktop.point(p&65535,p>>16);desktop.event(0x10,True)
            try:
                for _ in range(count):desktop.event(None,True);desktop.event(None,False)
            finally:desktop.event(0x10,False)
        else:
            for _ in range(count):
                u.SendMessageW(hwnd,0x201,5 if shift else 1,p);u.SendMessageW(hwnd,0x202,4 if shift else 0,p)
        row['wire']=barrier(None)
        def changed(pic):return [col for col in range(80) if tile(before,col,y)!=tile(pic,col,y)]
        # Settle even on old builds that highlight noncontiguous columns.
        wait_for(lambda:bool(changed(capture(return_pixels=True))))
        after=capture(phase+'-copied.png',return_pixels=True)
        row['highlight']=changed(after);row['previous_row_tail']=[col for col in (78,79) if tile(before,col,y-1)!=tile(after,col,y-1)]
        row['copied']=copy()
        row['passed']=(row['copied']==expected and row['highlight']==columns and row['previous_row_tail']==([79] if wrapped else []) and row['wire']=='1b5b306e'*2)
    return all(r['passed'] for r in rows)
