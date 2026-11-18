"""ReGIS native pixels through the single image, live renderers and presented GDI.

These are explicit geometry/lifecycle checks, separate from the unchanged
historical XTerm frame comparison. They do not claim full ReGIS conformance.
"""
import os
if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
    raise SystemExit('Native ReGIS checks require a GitHub-hosted runner')

from sixel_palette_window_smoke import main, reset, ESC, CSI, DCS, ST, BORDER, COLS, ROWS
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

    check('shared-regis-before',reset(False)+regis('S(E)S(M3(R0G100B0))W(I3)P[20,20]V[120,20]',1),expected(line(20)))
    red=expected(line(20,'red'))
    check('sixel-recolours-regis',DCS+'0;1q#3;2;100;0;0#3'+ST,red)
    expose('recoloured-regis-redraw',red)
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

if __name__=='__main__':
    main(background_exercise=exercise,suite_name='regis-window',
         font=os.environ['NEMOTERM_TEST_FONT'],before_exercise=before,
         profile_values=dict(NemoTabs=0))
