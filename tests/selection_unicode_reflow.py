"""A full-width glyph cannot straddle the margin, and its wrap pad is not text."""
from collections import Counter
from clipboard_test_utils import clipboard_text
from native_test_utils import u, wait_for, time


def verify(hwnd, begin, capture, resize, aim, barrier, desk, evidence):
    cw, ch = evidence['cell_pixels']
    ack = b'\x1b[0n'
    replies = b'\x1b[?47;2$y\x1b[?1002;1$y\x1b[?1006;1$y'
    rows = evidence['reflow_unicode'] = []
    text = '|ABQ中e\u0301V|'
    for tag, held in [('unicode-span', False), ('unicode-trailing-press', True)]:
        row = {'case': tag, 'frames': []}; rows.append(row)
        scene = ('\x1b[?1049l\x1bc\x1b[3J\x1b[?25l\x1b[3;1H' + text + ' e' +
                 '\x1b[7;70H' + text + '\x1b[1;1H\x1b[?1002;1006h\x1b[?47$p\x1b[?1002$p\x1b[?1006$p')
        begin(tag, scene, preserve_mouse=True)
        selected = set(range(4 if held else 3, 7))  # both halves of 中, e with its accent, optionally Q

        def frame(stage, cols, wanted):
            stride = 2 + cols*cw
            def inspect(raw):
                if len(raw) != stride*(2+24*ch)*3: return {}
                def tile(x,y):
                    data = b''.join(raw[3*((1+y*ch+i)*stride+1+x*cw):3*((1+y*ch+i)*stride+1+(x+1)*cw)] for i in range(ch))
                    vals = data[1::3]  # green channel; both palettes have contrasting text
                    bg = Counter(vals).most_common(1)[0][0]; contrast = max(vals)-min(vals)
                    return bg, tuple(abs(v-bg) > .22*contrast for v in vals)
                ref = [tile(i,2) for i in (*range(9),10)]  # include unaccented e as a negative control
                labels = ['|','A','B','Q','wide-L','wide-R','accent','V','|','base-e']
                actual = []; highlights = []
                for i in range(9):
                    pos = (i-4,7) if cols==74 and i>=4 else (69+i,6)
                    bg, mask = tile(*pos); ds = [sum(a!=b for a,b in zip(mask,t[1])) for t in ref]
                    actual.append(sorted({k for k,d in zip(labels,ds) if d==min(ds)}))
                    if bg!=ref[i][0]: highlights.append(i)
                pad_blank = not any(tile(73,6)[1]) if cols==74 else None
                return dict(glyphs=actual, highlight=highlights, pad_blank=pad_blank,
                            ok=actual==[[k] for k in labels[:9]] and highlights==sorted(wanted) and pad_blank is not False)
            until = time.monotonic()+2
            while not inspect(capture(return_pixels=True)).get('ok') and time.monotonic()<until: time.sleep(.05)
            obs = inspect(capture(tag+'-'+stage+'.png',return_pixels=True));row['frames'].append(dict(obs,stage=stage,cols=cols))

        try:
            frame('initial',80,set()); aim(74 if held else 72,6)
            desk.event(0x10,True);desk.event(None,True);wait_for(lambda:desk.state().capture==hwnd)
            if not held:
                aim(75,6);desk.event(None,False);desk.event(0x10,False);wait_for(lambda:desk.state().capture!=hwnd)
                frame('selected',80,selected)
            resize(-6,0)
            if held:
                desk.event(0x10,False);aim(2,7);desk.event(None,False);wait_for(lambda:desk.state().capture!=hwnd)
            row['gesture_wire'] = barrier(None)
            for stage,cols in [('narrow',74),('wide',80)]:
                if cols==80: resize(0,0)
                frame(stage,cols,selected); begin(tag+'-'+stage+'-copy','',preserve_mouse=True)
                seq = u.GetClipboardSequenceNumber();desk.chord(0x11,0x10,ord('C'));wire = barrier(None)
                row[stage] = dict(wire=wire,text=clipboard_text(hwnd) if u.GetClipboardSequenceNumber()!=seq else None)
            begin(tag+'-right','',preserve_mouse=True);aim(74,6);seq=u.GetClipboardSequenceNumber();desk.event('right',True)
            try: wait_for(lambda:desk.state().capture==hwnd or seq!=u.GetClipboardSequenceNumber())
            finally: desk.event('right',False)
            row['right']=dict(wire=barrier(None),text=clipboard_text(hwnd) if seq!=u.GetClipboardSequenceNumber() else None)
            want = dict(wire=(ack*2).hex(),text=('' if held else 'Q')+'中e\u0301')
            row['passed'] = all(f.get('ok') for f in row['frames']) and row['gesture_wire']==(replies+ack*2).hex() and all(row[k]==want for k in ('narrow','wide','right'))
        finally:
            for key in reversed(desk.held[:]): desk.event(key,False)
            resize(0,0)
    return all(r['passed'] for r in rows)
