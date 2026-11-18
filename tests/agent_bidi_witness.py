"""Verify copied characters from physical glyphs independently of the client's line layout."""
from collections import Counter
import hashlib
import io
import unicodedata
from PIL import Image
from clipboard_test_utils import clipboard_text
from native_test_utils import u, wait_for


def verify_bidi_copy(evidence, lines, wire, cw, ch, ox, oy, cols, image, desktop, frame, press, hwnd):
    # The same provider string is emitted in two possible orders by the
    # pinned clients. Identify which came down the wire before reading pixels.
    refs=('גְ','ב','א'); original='AאבגְZ';preordered='AגְבאZ'
    emitted,=[s for s in (original,preordered) if s.encode() in wire]
    suffix=emitted+' RגְR RבR RאR END_BIDI'
    row,=[i for i,line in enumerate(lines) if suffix in line]
    width=lambda s:sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in ('W','F') else 1 for c in s)
    x=width(lines[row].split(suffix,1)[0]);assert 0<x<x+16<cols
    logical_indices=(2,1,0) if emitted==original else (0,1,2)
    visual=logical_indices if evidence['client_visual_order'] else logical_indices[::-1]
    proof=evidence['bidi_system_copy']=dict(row=row,columns=[x,x+1],reference_columns=[x+7,x+11,x+15],
        emitted=emitted,wire_sha256=hashlib.sha256(wire).hexdigest(),expected_visual_order=visual)
    def tiles():
        bmp=image();pic=Image.open(io.BytesIO(bmp)).convert('RGB')
        y=oy+row*ch
        return bmp,[pic.crop((ox+c*cw,y,ox+(c+1)*cw,y+ch)).tobytes() for c in range(x-1,x+17)]
    def digest(t):return hashlib.sha256(t).hexdigest()
    def find_source():
        bmp,t=tiles();isolated=[t[i+1] for i in (7,11,15)]
        actual=[t[i+1] for i in (1,2,3)]
        proof.update(reference_digests=list(map(digest,isolated)),actual_digests=list(map(digest,actual)))
        if len(set(isolated))==3 and actual==[isolated[i] for i in visual]:return bmp,t
    bmp,source=wait_for(find_source);frame('bidi-source',bmp)
    proof['provider_layout_matches']=proof['actual_digests']==proof['reference_digests']
    def pixels(t):return list(zip(t[0::3],t[1::3],t[2::3]))
    source=list(map(pixels,source[:4]));bg=Counter(p for cell in source for p in cell).most_common(1)[0][0]
    def selected():
        bmp,after=tiles();after=list(map(pixels,after[:4]))
        colours=Counter(q for i in (1,2) for p,q in zip(source[i],after[i]) if p==bg)
        if not colours:return None
        fg=colours.most_common(1)[0][0];ratios=[]
        for i,(old,new) in enumerate(zip(source,after)):
            probes=[q for p,q in zip(old,new) if p==bg];want=fg if i in (1,2) else bg
            ratios.append(sum(q==want for q in probes)/len(probes) if probes else 0.)
        evidence['bidi_highlight']=dict(source=bg,selected=fg,cells=2,min_selected_ratio=min(ratios[1:3]),guard_ratios=[ratios[0],ratios[3]])
        if fg!=bg and min(ratios[1:3])>=.5 and min(ratios[0],ratios[3])>=.9:return bmp
    desktop.drag(ox+x*cw+cw//2,ox+(x+1)*cw+cw//2,oy+row*ch+ch//2,selected)
    frame('bidi-selected',wait_for(selected));seq=u.GetClipboardSequenceNumber();press(67,3)
    wait_for(lambda:u.GetClipboardSequenceNumber()!=seq);proof['copied']=clipboard_text(hwnd)
    proof['expected_copy']='A'+refs[visual[0]]
    assert proof['copied']==proof['expected_copy'],proof
