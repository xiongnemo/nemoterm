"""Erase a tall opaque page by visible bands. A stored graphic on the other screen must survive."""
import math
import os
from regis_window_smoke import before, context, main, regis, reset, CSI, BORDER, COLS, ROWS, u


def exercise(phase, block):
    cw,ch=context['cell_pixels']; width=min(800,(cw*COLS)//32*32);height=8192
    assert width*height*2>4*1024*1024 and width<=cw*COLS,(width,ch)
    blank=dict(x=BORDER,y=BORDER,width=160,height=120,colour='black')
    def line(y,colour):return dict(x=BORDER+20,y=BORDER+y,width=101,height=1,colour=colour)
    def frame(label,wire,*lines):phase(label,wire,[blank,*lines],expected_reply=b'')
    # Keep a visually distinct graphic on the alternate screen. No further ReGIS commands
    # may rebuild it after that screen is restored.
    red=regis('S(E)S(M2(R100G0B0))W(I2)P[20,40]V[120,40]',1)
    frame('stored-red-line',reset()+CSI+'?47h'+red,line(40,'red'))
    green=regis(f'S(A[0,0][{width-1},{height-1}])S(E)S(M3(R0G100B0))W(I3)P[20,20]V[120,20]',1)
    frame('active-green-line',CSI+'?47l'+green,line(20,'green'))
    stripe=''.join(CSI+f'{r};1H'+CSI+'2K' for r in range(1,ROWS+1));scroll=CSI+f'{ROWS}S'
    bands=math.ceil(height/(ROWS*ch));context['checks'][-1].update(page=[width,height],band_pixels=ROWS*ch,bands=bands)
    frame('first-band-erased',stripe)
    # Separate barriers bound each batch, and the configured main-screen history is
    # longer than the entire page. History eviction cannot free the already erased ink.
    for start in range(1,bands,6):frame(f'erased-through-band-{min(start+6,bands)}',(scroll+stripe)*min(6,bands-start))
    frame('stored-red-line-restored',CSI+'?47h',line(40,'red'))
    assert u.RedrawWindow(context['session']['hwnd'],None,None,0x185)
    frame('stored-red-line-after-repaint','',line(40,'red'))


if __name__=='__main__':
    main(exercise,suite_name='regis-erase-pressure',font=os.environ['NEMOTERM_TEST_FONT'],before_exercise=before,
         profile_values=dict(NemoTabs=0,ScrollbackLines=5000,FontHeight=16))
