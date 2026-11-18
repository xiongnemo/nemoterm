"""Retained ReGIS pixels at a one-line main-screen history limit."""
from regis_window_smoke import before, context, regis, reset, CSI, BORDER, COLS, ROWS, main, os, u, w, c


def exercise(phase, block):
    _,ch=context['cell_pixels']
    # A and B are consecutive pixel rows on opposite sides of the eviction
    # boundary. C stays visible. The child DSR barrier precedes every capture.
    a,b,d=2*ch-1,2*ch,3*ch+5
    assert d<120 and (ROWS-3)*ch>=120
    roi=dict(x=BORDER,y=BORDER,width=160,height=120,colour='black')
    def rows(*ys):
        return [roi]+[dict(x=BORDER+20,y=BORDER+y,width=101,height=1,colour='green') for y in ys if y>=0]
    def stroke(y):return f'P[20,{y}]V[120,{y}]'
    setup=reset()+regis('S(E)S(M3(R0G100B0))W(I3)'+''.join(map(stroke,(a,b,d))),1)
    def check(label,seq,ys,grid=(COLS,ROWS)):
        phase(label,seq,rows(*ys),expected_reply=b'',grid=grid)
    def redraw(label,ys):
        assert u.RedrawWindow(context['session']['hwnd'],None,None,0x185)
        check(label,'',ys)

    check('one-line-history-setup',setup,(a,b,d))
    check('three-rows-up',CSI+'3S',(d-3*ch,))
    check('reverse-with-one-saved-row',CSI+'3T',(b,d))
    redraw('reverse-survives-repaint',(b,d))
    # The current page still accepts drawing into a discarded source row. It
    # must be cleared again if a later scroll crosses the same boundary.
    check('draw-new-ink-in-expired-row',regis('W(I3)'+stroke(a)),(a,b,d))
    check('second-scroll-up',CSI+'3S',(d-3*ch,))
    check('new-ink-expires-again',CSI+'3T',(b,d))

    check('bounded-resize-setup',setup+CSI+f'{ROWS};1H',(a,b,d))
    hwnd=context['session']['window'];rect=w.RECT();assert u.GetWindowRect(hwnd,c.byref(rect))
    width,height=rect.right-rect.left,rect.bottom-rect.top
    assert u.SetWindowPos(hwnd,None,0,0,width,height-3*ch,0x16)
    check('shrink-three-rows','',(d-3*ch,),(COLS,ROWS-3))
    assert u.SetWindowPos(hwnd,None,0,0,width,height,0x16)
    check('grow-restores-only-one-row','',(0,d-2*ch))
    check('reverse-after-bounded-resize',CSI+'2T',(b,d))
    redraw('bounded-resize-survives-repaint',(b,d))


if __name__=='__main__':
    main(background_exercise=exercise,suite_name='regis-window-history-limit',
         font=os.environ['NEMOTERM_TEST_FONT'],before_exercise=before,
         profile_values=dict(NemoTabs=0,ScrollbackLines=1,ReGISScrollWithText=1))
