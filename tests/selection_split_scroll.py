"""A split TUI scrolls logical columns; Shift selects the painted glyphs."""
from collections import Counter
from native_test_utils import u, wait_for


COLOURS = ('42;72;100','80;45;71','43;86;49','101;54;41','61;43;102')
TEXT = ('L','\u05d0','\u05d1','\u05d2\u05b0','R')


def coloured(chars):
    return ''.join('\x1b[48;2;'+rgb+'m'+ch for rgb,ch in zip(COLOURS,chars))+'\x1b[0m'


def verify(hwnd, begin, point, capture, tile, copy, barrier, evidence, desktop=None):
    records = evidence['split_scroll_system' if desktop else 'split_scroll_press'] = []
    def background(pic,x,y):
        t=tile(pic,x,y)
        return Counter(t[i:i+3] for i in range(0,len(t),3)).most_common(1)[0][0]

    for down in (True, False):
        for inside in (True, False):
            for block in (False, True):
                if desktop and (down,inside,block) not in ((True,True,True),(False,False,False)):
                    continue
                name=('split-system-' if desktop else 'split-')+('down' if down else 'up')+('-moving' if inside else '-stationary')+('-block' if block else '-stream')
                y=12 if block else 8; dest=y+(1 if down else -1); key_row=20
                # Margins start at logical column 6 (zero based). A glyph at
                # visual column 5 moves with the pane; the one at 7 stays put.
                setup=(f'\x1bc\x1b[?25l\x1b[{y};5HLabcR\x1b[{y+1};5H'+coloured(TEXT)+
                       f'\x1b[{y+2};5HLxyzR\x1b[{key_row+1};1H'+coloured('     ')+
                       '\x1b[?69h\x1b[7;30s\x1b[5;17r\x1b[?1002;1006h')
                begin(name+'-draw',setup)
                row=dict(case=name);records.append(row)
                def source():
                    p=capture(return_pixels=True);k=[background(p,x,key_row) for x in range(5)]
                    return k if len(set(k))==5 and [background(p,x,y) for x in range(4,9)]==[k[i] for i in (0,3,2,1,4)] else None
                keys=wait_for(source)
                row['pressed']=[5 if inside else 7,y];target_y=dest if inside else y
                row['released']=[7 if inside else 4,target_y]
                def system_point(cell):
                    pt=point(*cell);return desktop.point(pt & 0xffff,pt >> 16)
                if desktop:
                    system_point(row['pressed']);desktop.event(0x10,True)
                    if block:desktop.event(0x11,True)
                    desktop.event(None,True);wait_for(lambda:desktop.state().capture==hwnd)
                else:u.SendMessageW(hwnd,0x201,13 if block else 5,point(*row['pressed']))
                try:
                    begin(name+'-scroll','\x1b[1'+('T' if down else 'S'))
                    def moved():
                        p=capture(return_pixels=True)
                        return p if (background(p,5,y)==keys[1] and background(p,6,dest)==keys[3] and background(p,7,dest)==keys[2]) else None
                    normal=wait_for(moved);row.update(moving_glyph=[6,dest],stationary_glyph=[5,y]);capture('selection-'+name+'-source.png')
                    if desktop:
                        if block:desktop.event(0x11,False)
                        desktop.event(0x10,False);system_point(row['released'])
                    else:u.SendMessageW(hwnd,0x200,1,point(*row['released']))
                finally:
                    if desktop:
                        desktop.event(None,False);wait_for(lambda:desktop.state().capture!=hwnd)
                    else:u.SendMessageW(hwnd,0x202,0,point(*row['released']))
                row['copied']=copy();row['wire']=barrier()
                row['expected']=TEXT[2]+TEXT[3] if inside else TEXT[0]+TEXT[1]
                def highlight():
                    p=capture(return_pixels=True)
                    return [[x for x in range(3,12) if tile(p,x,a)!=tile(normal,x,a)] for a in sorted((y,dest))]
                want=[6,7] if inside else [4,5]
                row['expected_highlight']=[want if a==target_y else [] for a in sorted((y,dest))]
                # Copy has completed; allow the renderer to present its selection.
                first=highlight();row['first_highlight']=first
                if first!=row['expected_highlight']:
                    try: wait_for(lambda:highlight()==row['expected_highlight'],timeout=1)
                    except AssertionError: pass
                row['highlighted']=highlight();capture('selection-'+name+'-selected.png')
                row['passed']=(row['copied']==row['expected'] and row['highlighted']==row['expected_highlight'])
    assert all(r['passed'] for r in records),records
