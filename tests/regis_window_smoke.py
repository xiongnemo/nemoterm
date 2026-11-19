"""ReGIS native pixels through the single image, live renderers and presented GDI.

These are explicit geometry/lifecycle checks, separate from the unchanged
historical XTerm frame comparison. They do not claim full ReGIS conformance.
"""
import os
import hashlib
if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
    raise SystemExit('Native ReGIS checks require a GitHub-hosted runner')

from sixel_palette_window_smoke import main, reset, ESC, CSI, DCS, ST, BORDER, COLS, ROWS
from sixel_palette_window_smoke import api
from native_test_utils import u, w, c

u.RedrawWindow.argtypes=[w.HWND,c.c_void_p,w.HANDLE,w.UINT]
u.GetWindowRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
u.SetWindowPos.argtypes=[w.HWND,w.HWND,c.c_int,c.c_int,c.c_int,c.c_int,w.UINT]
context={}

def before(evidence):
    context.update(evidence)

def regis(body,mode=0):
    return DCS+str(mode)+'p'+body+ST

def exercise(phase,block):
    cw,ch=context['cell_pixels']
    width,height=context['image_size']
    assert width>=162 and height>=122 and ch<40
    roi=dict(x=BORDER,y=BORDER,width=160,height=120,colour='black')

    def line(y,colour='green',x=20,count=101):
        return dict(x=BORDER+x,y=BORDER+y,width=count,height=1,colour=colour)

    def expected(*lines):
        return [roi]+[r for r in lines if BORDER<=r['y']<BORDER+120]

    def check(name,wire,regions,reply=b''):
        phase(name,wire,regions,expected_reply=reply)

    def expose(name,regions):
        assert u.RedrawWindow(context['session']['hwnd'],None,None,0x185)
        check(name,'',regions)

    setup=reset()+regis('S(E)S(M3(R0G100B0))W(I3)P[20,20]V[120,20]P[20,80]V[120,80]',1)
    both=expected(line(20),line(80))
    check('draw-two-lines',setup,both)
    check('position-report',regis('R(P)'),both,b'[120,80]\r')
    expose('redraw-two-lines',both)

    remaining=expected(line(80))
    check('erase-line',CSI+f'{20//ch+1};1H'+CSI+'2K',remaining)
    expose('erase-line-survives-redraw',remaining)
    check('erase-display',CSI+'2J',expected())
    expose('erase-display-survives-redraw',expected())

    check('scroll-up-before',setup,both)
    moved=expected(line(20-3*ch),line(80-3*ch))
    check('scroll-up',CSI+'3S',moved)
    expose('scroll-up-redraw',moved)
    # The pinned parser maps a new origin-zero page on the next request.
    # Its independent full repaint is blank; no old presented pixels remain.
    check('scroll-up-new-page',regis('R(P)'),expected(),b'[120,80]\r')
    expose('scroll-up-new-page-redraw',expected())

    check('scroll-down-before',setup,both)
    moved=expected(line(20+3*ch),line(80+3*ch))
    check('scroll-down',CSI+'3T',moved)
    expose('scroll-down-redraw',moved)

    check('page-before',setup,both)
    check('hidden-page-write',regis('P(P1)S(M3(R0G0B100))P[20,60]V[120,60]'),both)
    blue=expected(line(60,'blue'))
    check('show-second-page',regis('S(P1)'),blue)
    expose('second-page-redraw',blue)
    check('restore-first-page',regis('S(P0)'),both)
    check('alternate-screen',CSI+'?1049h'+regis('S(E)S(M3(R100G0B0))W(I3)P[20,40]V[120,40]',1),expected(line(40,'red')))
    check('restore-main-screen',CSI+'?1049l',both)

    # Check both actual text cells and independent graphic pixels. Markers are
    # placed outside the pixel ROI so the font cannot change the geometric test.
    assert 34*cw >= roi['width']
    alt_line=expected(line(80,'red'))
    markers={'main':'M1X','alt':'A2Y','empty':''}
    text_pos=CSI+'1;35H'
    def bank(name,wire,pixels,which):
        check(name,wire,pixels)
        text=api.request(context['endpoint'],'text',context['session']['id'])
        observed={m for m in markers.values() if m and m in text}
        want={markers[which]} if markers[which] else set()
        record=context['checks'][-1]
        record.update(expected_markers=sorted(want),observed_markers=sorted(observed))
        assert observed==want,(name,observed,want)
    for mode in (1047,1049):
        tag=f'alt-{mode}-'; enter=CSI+f'?{mode}h'; leave=CSI+f'?{mode}l'
        bank(tag+'main',reset()+text_pos+markers['main'],expected(),'main')
        bank(tag+'enter',enter,expected(),'empty')
        bank(tag+'write',text_pos+markers['alt']+regis(
            'S(E)S(M2(R100G0B0))W(I2)P[20,80]V[120,80]',1),alt_line,'alt')
        bank(tag+'repeat',enter,alt_line if mode==1047 else expected(),
             'alt' if mode==1047 else 'empty')
        bank(tag+'leave',leave,expected(),'main')
        bank(tag+'redundant-leave',leave,expected(),'main')
        bank(tag+'reenter',enter,expected(),'empty')
        bank(tag+'finish',leave,expected(),'main')

    # The ReGIS canvas can occlude valid text cells. Check a separate text-only
    # bank with the actual pixels of this renderer, including the presented DC.
    glyphs={}
    def text_pixels(name,wire,key,learn=False):
        def inspect(record,width,bgra):
            left=BORDER+34*cw
            glyph=b''.join(bgra[4*(y*width+left+x):4*(y*width+left+x)+3]
                           for y in range(BORDER,BORDER+ch) for x in range(3*cw))
            digest=hashlib.sha256(glyph).hexdigest()
            def ink(row,col):
                i=3*(row*3*cw+col)
                return any(glyph[i:i+3])
            counts=[sum(ink(y,x) for y in range(ch) for x in range(cell*cw,(cell+1)*cw))
                    for cell in range(3)]
            record['marker_strip']=dict(bank=key,cell_ink=counts,bgr_sha256=digest,learn=learn)
            if key=='empty':return not any(counts)
            if not all(counts):return False
            if learn:glyphs[key]=digest
            return digest==glyphs[key]
        phase(name,wire,expected(),expected_reply=b'',stable_seconds=.12,pixel_check=inspect)
    for mode in (1047,1049):
        tag=f'text-{mode}-';enter=CSI+f'?{mode}h';leave=CSI+f'?{mode}l'
        text_pixels(tag+'main',reset()+text_pos+'M1X','main',True)
        text_pixels(tag+'enter',enter,'empty')
        text_pixels(tag+'write',text_pos+'A2Y','alt',True)
        assert glyphs['main']!=glyphs['alt']
        text_pixels(tag+'repeat',enter,'alt' if mode==1047 else 'empty')
        text_pixels(tag+'leave',leave,'main')
        text_pixels(tag+'redundant-leave',leave,'main')
        text_pixels(tag+'reenter',enter,'empty')
        text_pixels(tag+'finish',leave,'main')

    check('shared-regis-before',reset(False)+regis('S(E)S(M3(R0G100B0))W(I3)P[20,20]V[120,20]',1),expected(line(20)))
    red=expected(line(20,'red'))
    check('sixel-recolours-regis',DCS+'0;1q#3;2;100;0;0#3'+ST,red)
    expose('recoloured-regis-redraw',red)
    # Keep the retained ReGIS line. Read a pending/committed colour again via
    # new Sixel pixels on a different row, including after native invalidation.
    def swatch(col, colour):
        return dict(x=BORDER+col*cw,y=BORDER+2*ch,width=12,height=6,colour=colour)
    green_setup=reset(False)+regis('S(E)S(M3(R0G100B0))W(I3)P[20,20]V[120,20]',1)
    check('shared-st-pending',green_setup+DCS+'9;1q#3;2;100;0;0'+ST,expected(line(20)))
    green_read=expected(line(20),swatch(2,'green'))
    check('shared-st-fresh-read',CSI+'3;3H'+DCS+'9;1q#3!12~'+ST,green_read)
    expose('shared-st-fresh-read-redraw',green_read)
    red_read=expected(line(20,'red'),swatch(2,'red'),swatch(6,'red'))
    check('shared-dollar-fresh-read',DCS+'9;1q#3;2;100;0;0$'+ST+
          CSI+'3;7H'+DCS+'9;1q#3!12~'+ST,red_read)
    expose('shared-dollar-fresh-read-redraw',red_read)
    check('shared-sixel-before',reset(False)+DCS+'0;1q#3;2;0;100;0!100~'+ST,
          expected(dict(x=BORDER,y=BORDER,width=100,height=6,colour='green')))
    red_raster=expected(dict(x=BORDER,y=BORDER,width=100,height=6,colour='red'))
    check('regis-recolours-sixel',regis('S(M3(R100G0B0))',1),red_raster)
    expose('recoloured-sixel-redraw',red_raster)
    check('hard-reset',ESC+'c'+CSI+'?25l',expected())
    expose('hard-reset-redraw',expected())

    check('continued-alternate-before',setup,both)
    check('continued-alternate-draw',CSI+'?1049h'+regis(
        'S(E)S(M3(R100G0B0))W(I3)P[20,40]V[120,40]'),expected(line(40,'red')))
    check('continued-alternate-restore',CSI+'?1049l',both)
    expose('continued-alternate-restore-redraw',both)

    check('margin-scroll-before',setup,both)
    # Row one is outside this region. Scroll its lower line by one text row
    # while preserving the upper line and its exact pixel coordinates.
    top=20//ch+2
    assert top*ch<=80 and 80-ch>20
    check('margin-scroll',CSI+f'{top};12r'+CSI+'1S',expected(line(20),line(80-ch)))
    expose('margin-scroll-redraw',expected(line(20),line(80-ch)))

    # ED 3 clears saved lines, leaving the current screen intact. Reverse
    # scrolling makes previously off-screen source pixels observable again.
    assert 20 < 3*ch <= 80
    live=expected(line(80-3*ch))
    for from_alt in (False,True):
        case='history-clear-'+('from-alt' if from_alt else 'main')
        check(case+'-setup',setup,both)
        check(case+'-scroll-to-history',CSI+'3S',live)
        if from_alt:
            alternate=expected(line(40,'red'))
            check(case+'-alt',CSI+'?1049h'+regis('S(E)S(M3(R100G0B0))W(I3)P[20,40]V[120,40]',1),alternate)
            check(case+'-erase-saved',CSI+'3J',alternate)
            check(case+'-restore-main',CSI+'?1049l',live)
        else:
            check(case+'-erase-saved',CSI+'3J',live)
        check(case+'-reverse-scroll',CSI+'3T',expected(line(80)))
        expose(case+'-redraw',expected(line(80)))

    # Resizing from the bottom puts existing main-screen rows into temporary
    # history; growing the window pulls the same rows back. With the cursor
    # at the top, the same pair of resizes should leave these pixels in place.
    hwnd=context['session']['window']
    rect=w.RECT()
    assert u.GetWindowRect(hwnd,c.byref(rect))
    outer_w,outer_h=rect.right-rect.left,rect.bottom-rect.top
    for at_bottom in (True,False):
        case='resize-'+('saved' if at_bottom else 'blank-tail')
        check(case+'-setup',setup+CSI+f'{ROWS if at_bottom else 1};1H',both)
        short=ROWS-2
        assert short*ch>=120
        assert u.SetWindowPos(hwnd,None,0,0,outer_w,outer_h-2*ch,0x16)
        moved=expected(line(20-2*ch),line(80-2*ch)) if at_bottom else both
        phase(case+'-shrink','',moved,expected_reply=b'',grid=(COLS,short))
        assert u.RedrawWindow(context['session']['hwnd'],None,None,0x185)
        phase(case+'-shrink-redraw','',moved,expected_reply=b'',grid=(COLS,short))
        assert u.SetWindowPos(hwnd,None,0,0,outer_w,outer_h,0x16)
        check(case+'-grow','',both)
        expose(case+'-grow-redraw',both)

    private_sequence(phase,block)


def private_sequence(phase,block,legacy=False):
    # These four frames belong to ONE process. The wire (including each RIS)
    # and both halves were independently captured on stock XTerm 412.
    import json
    from pathlib import Path
    import zipfile
    archive=Path(__file__).resolve().parents[1]/'testdata/upstream'/'xterm-private-reset-chain.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()=='5bebdfbee826558be3a9e53cd57795bb5d24796823c8f6a9dc6241eeb75e83ef'
    with zipfile.ZipFile(archive) as original:
        steps=json.loads(original.read('observations/private-reset-chain-whole/observed.json'))['steps']
    cw=context['cell_pixels'][0]
    roi=dict(x=BORDER,y=BORDER,width=160,height=120,colour='black')
    shapes=[('identity','#1;2;100;0;0!8~#2;2;100;0;0!8~'),
            ('overwrite','#1;2;100;0;0!16~$#2;2;0;0;100!8~')]
    assert len(steps)==4
    for idx,step in enumerate(steps):
        shape,paint=shapes[idx//2]; delimiter='$' if idx%2 else ''
        wire=reset()+CSI+'2;4H'+DCS+'0;1q'+paint+'#1;2;0;100;0'+delimiter+ST
        assert wire.encode('ascii').hex()==step['sequence_hex']
        green='green' if legacy else 'vt340-green'
        left='blue' if shape=='overwrite' else green if delimiter else 'red'
        right=green if shape=='overwrite' and delimiter else 'red'
        if not legacy:
            rgb={'red':(255,0,0),'blue':(0,0,255),'vt340-green':(51,204,51)}
            counts={tuple(colour):count for count,colour in step['repaint']['colours'] if any(colour)}
            assert counts=={rgb[c]:48*(int(c==left)+int(c==right)) for c in (left,right)}
        regions=[roi,block(2,left,cw,8),block(2,right,cw+8,8)]
        name='private-register-'+shape+('-dollar' if delimiter else '-st')
        phase(name,wire,regions,expected_reply=b'')
        assert u.RedrawWindow(context['session']['hwnd'],None,None,0x185)
        phase(name+'-redraw','',regions,expected_reply=b'')

if __name__=='__main__':
    main(background_exercise=exercise,suite_name='regis-window',
         font=os.environ['NEMOTERM_TEST_FONT'],before_exercise=before,
         profile_values=dict(NemoTabs=0,ReGISScrollWithText=1))
