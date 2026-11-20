"""Observe two identical typed glyphs, then their removal, on the owned presentation surface."""
from collections import Counter
import hashlib
import struct
from native_test_utils import u, wait_for
from presented_window_capture import PresentedWindowCapture


def verify_composer_edit(pid, hwnd, directx, desktop, text, width, grid, cell, origin, prefix, frame, receipt):
    cols,rows = grid; cw,ch = cell; ox,oy=origin
    capture=PresentedWindowCapture(pid,hwnd,directx,raise_window=False)
    typo=prefix+'xx'; receipt.update(typed=typo, frames={})
    try:
        capture.wait_for_initial_geometry()
        desktop.chord(ord('X'));desktop.chord(ord('X'))
        screen=wait_for(lambda:s if typo in (s:=text()) else None)
        (y,line),=[(i,l) for i,l in enumerate(screen.split('\n')) if typo in l]
        x=width(line.split(typo,1)[0]+prefix)
        assert 0<=y<rows and 0<=x<x+1<cols
        receipt.update(column=x,row=y,cell=[cw,ch],origin=[ox,oy])
        def read(glyph_cells):
            bmp=capture.capture();w,neg_h=struct.unpack_from('<ii',bmp,18)
            assert w>=ox+(x+2*glyph_cells)*cw and -neg_h>=oy+(y+1)*ch
            shapes=[]
            for col in (x,x+glyph_cells):
                # Exclude caret edge / underline. A solid block also has a uniform interior.
                tile=[bmp[54+i*4:57+i*4] for yy in range(2,ch-3) for xx in range(1,glyph_cells*cw-1)
                      for i in [(oy+y*ch+yy)*w+ox+col*cw+xx]]
                bg=Counter(tile).most_common(1)[0][0]
                shapes.append(bytes(max(abs(a-b) for a,b in zip(pixel,bg))>24 for pixel in tile))
            return bmp,shapes
        def stage(name,predicate,glyph_cells=1):
            last=None
            def probe():
                nonlocal last
                bmp,shapes=read(glyph_cells);last=(bmp,shapes)
                if predicate(*shapes):return last
            try:bmp,shapes=wait_for(probe)
            except AssertionError:
                if last: frame('composer-unmatched-'+name,last[0])
                raise
            frame('composer-'+name,bmp)
            receipt['frames'][name]=dict(ink=[sum(s) for s in shapes],mask_sha256=[hashlib.sha256(s).hexdigest() for s in shapes])
            return shapes
        original,_=stage('before-backspace',lambda a,b:a==b and sum(a)>=5)
        desktop.chord(0x08);wait_for(lambda:prefix+'x' in (s:=text()) and typo not in s)
        stage('one-backspace',lambda a,b:a==original and not any(b))
        desktop.chord(0x08);wait_for(lambda:prefix.rstrip() in (s:=text()) and prefix+'x' not in s)
        stage('after-backspace',lambda a,b:not any(a) and not any(b))
        # One Win32 text message with count two must reach the real composer as
        # two independently editable, double-width characters. Physical keys
        # above and below are separate from the controlled character message.
        repeat=receipt['character_repeat']=dict(message='WM_CHAR',scalar=0x4e2d,count=2)
        assert x+4<=cols
        u.SendMessageW(hwnd,0x102,0x4e2d,2)
        def count_is(count):
            for line in text().splitlines():
                if prefix not in line: continue
                suffix=line.split(prefix,1)[1]
                repeat['last_count']=len(suffix)-len(suffix.lstrip('中'))
                if repeat['last_count']==count: return True
            return False
        wait_for(lambda:count_is(2))
        full,_=stage('repeated-han',lambda a,b:a==b and sum(a)>=5,2)
        desktop.chord(0x08);wait_for(lambda:count_is(1))
        stage('one-han',lambda a,b:a==full and not any(b),2)
        desktop.chord(0x08);wait_for(lambda:count_is(0))
        stage('removed-han',lambda a,b:not any(a) and not any(b),2)
        repeat['counts']=[2,1,0]
        desktop.target();receipt['corrected']=True
    finally:
        receipt['capture']=capture.close()
