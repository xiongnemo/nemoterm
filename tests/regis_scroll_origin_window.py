"""Compare full-screen text motion and the ReGIS page origin on an owned Windows window."""
import os
import sys
from regis_window_smoke import before, context, main, regis, reset, CSI, ESC, BORDER, api, u

PROFILES={
    'fresh':({},False), 'old':({'Present':1},True),
    'anchor':({'Present':1,'ReGISScrollWithText':0},False),
    'follow':({'Present':1,'ReGISScrollWithText':1},True),
}

if __name__=='__main__':
    profile=sys.argv.pop(1)
    values,follow=PROFILES[profile]
    def exercise(phase,block):
        ch=context['cell_pixels'][1]
        blank=dict(x=BORDER,y=BORDER,width=160,height=120,colour='black')
        def frame(name,wire,lines,rows,reply=b''):
            regions=[blank]+[dict(x=BORDER+20,y=BORDER+y,width=101,height=1,colour=c)
                             for y,c in lines if 0<=y<120]
            phase(name,wire,regions,expected_reply=reply)
            text=api.request(context['endpoint'],'text',context['session']['id']).splitlines()
            observed=[(i+1,v[31:32]) for i,v in enumerate(text) if v[31:32] in ('A','B')]
            expected=list(zip(rows,('A','B')))
            context['checks'][-1].update(marker_rows=observed,expected_marker_rows=expected)
            assert observed==expected,(name,observed,expected)
        def green(offset=0): return [(20+offset,'green'),(80+offset,'green')]
        pos=b'[120,80]\r'
        for key,operation in [('sd',CSI+'2T'),('ri',ESC+'M'+ESC+'M'),('il',CSI+'2L'),('su',CSI+'2S')]:
            setup=CSI+'3;32HA'+CSI+'7;32HB'+CSI+'H'+regis(
                'S(E)S(M3(R0G100B0))W(I3)P[20,20]V[120,20]P[20,80]V[120,80]R(P)',1)
            frame(key+'-draw',reset()+setup,green(),(3,7),pos)
            up=key=='su'; rows=(1,5) if up else (5,9)
            offset=-2*ch if up else 2*ch if follow else 0
            frame(key+'-move',operation+CSI+'6n',green(offset),rows,b'\x1b[1;1R')
            assert u.RedrawWindow(context['session']['hwnd'],None,None,0x185)
            frame(key+'-repaint','',green(offset),rows)
            kept=[] if offset else green()
            frame(key+'-query',regis('R(P)'),kept,rows,pos)
            frame(key+'-draw-again',regis('S(M2(R100G0B0))W(I2)P[20,50]V[120,50]R(P)'),
                  kept+[(50,'red')],rows,b'[120,50]\r')
        # A page which has already scrolled up is a stronger control than a
        # pristine origin-zero page. ED 3 must not bring expired ink back.
        for from_alt in (False,True):
            label='history-alt' if from_alt else 'history-main'
            wire=reset()+CSI+'5;32HA'+CSI+'9;32HB'+CSI+'H'+regis(
                'S(E)S(M3(R0G100B0))W(I3)P[20,20]V[120,20]P[20,80]V[120,80]',1)
            frame(label+'-draw',wire,green(),(5,9))
            frame(label+'-up',CSI+'3S',green(-3*ch),(2,6))
            wire=CSI+'?1049h'+CSI+'3J'+CSI+'?1049l' if from_alt else CSI+'3J'
            frame(label+'-clear-history',wire,green(-3*ch),(2,6))
            frame(label+'-reverse',CSI+'3T',[(80 if follow else 80-3*ch,'green')],(5,9))
    main(exercise,suite_name='regis-window-scroll-origin-'+profile,before_exercise=before,
         font=os.environ['NEMOTERM_TEST_FONT'],profile_values=dict(NemoTabs=0,**values))
