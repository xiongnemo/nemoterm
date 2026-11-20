"""Read a physical two-row block selection in the actual agent's rendered reply."""
import io
import time
from PIL import Image, ImageChops
from clipboard_test_utils import clipboard_text, set_clipboard
from native_test_utils import u, wait_for
from presented_window_capture import PresentedWindowCapture


def verify_rectangle(evidence, text, desk, frame, pid, hwnd, renderer, cw, ch, ox, oy, width):
    markers = ('BOX1|中文|Z', 'BOX2|abcd|Z')
    rec = evidence['chinese_rectangle'] = dict(markers=markers, cell=[cw,ch], origin=[ox,oy])
    def locate():
        lines = text().split('\n')
        rows = [[i for i,s in enumerate(lines) if m in s] for m in markers]
        if any(len(r) != 1 for r in rows): return None
        a,b = rows[0][0],rows[1][0]
        starts = [width(lines[y].split(m,1)[0])+5 for y,m in zip((a,b),markers)]
        rec.update(rows=[a,b], columns=starts)
        if b == a+1 and starts[0] == starts[1]: return a,starts[0]
    y,x = wait_for(locate)
    cam = PresentedWindowCapture(pid,hwnd,directx=renderer==2,raise_window=False)
    rec['camera'] = cam.record
    def rect(col,row,n=1): return (ox+col*cw,oy+row*ch,ox+(col+n)*cw,oy+(row+1)*ch)
    def capture():
        bmp = cam.capture(); return bmp,Image.open(io.BytesIO(bmp)).convert('RGB')
    def point(col,row): desk.point(ox+col*cw+cw//2,oy+row*ch+ch//2)
    try:
        cam.wait_for_initial_geometry(); prior=None; since=0
        def settled():
            nonlocal prior,since
            bmp,pic=capture(); tile=pic.crop((ox+(x-1)*cw,oy+y*ch,ox+(x+5)*cw,oy+(y+2)*ch)).tobytes()
            now=time.monotonic()
            if tile!=prior: prior,since=tile,now
            if now-since>.15 and all(len(pic.crop(rect(x,r,4)).getcolors(4*cw*ch))>1 for r in (y,y+1)):
                return bmp,pic
        bmp,base=wait_for(settled); frame('rectangle-source',bmp)
        # Select only the two inner columns: on the upper row both touched
        # double-width characters expand; on the lower row only b and c do.
        ends=[(x+1,y),(x+2,y+1)]
        if renderer==2: ends.reverse()
        rec['drag']=ends; start_event=len(desk.record['events']); point(*ends[0])
        desk.event(0x10,True);desk.event(0x11,True);desk.event(None,True)
        wait_for(lambda:desk.state().capture==hwnd);point(*ends[1]); last=None
        def painted():
            nonlocal last
            last,pic=capture(); ratios=[]; good=True
            for i,selected in enumerate(({0,1,2,3},{1,2})):
                rr=[]
                for j in range(-1,5):
                    tile=rect(x+j,y+i); dr,dg,db=ImageChops.difference(base.crop(tile),pic.crop(tile)).split()
                    ratio=1-ImageChops.lighter(ImageChops.lighter(dr,dg),db).histogram()[0]/(cw*ch)
                    rr.append(ratio)
                    if not (ratio>.5 if j in selected else ratio<.1): good=False
                ratios.append(rr)
            rec['changed_cell_ratios']=ratios
            return last if good else None
        try: frame('rectangle-selected',wait_for(painted))
        except Exception:
            if last: frame('rectangle-unmatched',last)
            raise
        finally:
            for k in (None,0x11,0x10):
                if k in desk.held: desk.event(k,False)
        wait_for(lambda:desk.state().capture!=hwnd)
        # Replace mouse-up auto-copy; only the physical Copy shortcut can pass.
        set_clipboard(hwnd,'UNSELECTED_BOX'); seq=u.GetClipboardSequenceNumber();desk.chord(0x11,0x10,ord('C'))
        wait_for(lambda:u.GetClipboardSequenceNumber()!=seq);rec['clipboard']=clipboard_text(hwnd)
        rec['events']=desk.record['events'][start_event:];assert rec['clipboard']=='中文\r\nbc',rec['clipboard']
    finally: cam.close()
