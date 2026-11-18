"""Discriminate a ReGIS page remap from an ordinary cursor-position query."""
import os
import sys
from regis_window_smoke import before, main, regis, reset, CSI, BORDER

if __name__=='__main__':
    query=sys.argv.pop(1)
    assert query in ('text','graphics')
    def exercise(phase,block):
        black=dict(x=BORDER,y=BORDER,width=160,height=120,colour='black')
        def check(name,wire,ink=None,reply=b''):
            regions=[black]
            if ink:
                colour,y=ink
                regions.append(dict(x=BORDER+20,y=BORDER+y,width=101,height=1,colour=colour))
            phase(name,wire,regions,expected_reply=reply)
        green=('green',20); red=('red',80); position=b'[120,80]\r'
        check('main-line',reset()+regis('S(E)S(M3(R0G100B0))W(I3)P[20,20]V[120,20]',1),green)
        check('enter',CSI+'?1049h')
        check('alternate-line',regis('S(E)S(M2(R100G0B0))W(I2)P[20,80]V[120,80]R(P)'),red,position)
        # Product guarantee: main is visible on return even before a graphics query.
        check('leave',CSI+'?1049l',green)
        if query=='graphics': check('main-query',regis('R(P)'),green,position)
        else: check('main-query',CSI+'6n',green,b'\x1b[1;1R')
        check('clear-on-entry',CSI+'?1049h')
        check('remap-alternate',regis('R(P)'),red if query=='graphics' else None,position)
        check('erase-active-page',CSI+'2J')
        check('after-erase',regis('R(P)'),None,position)
        check('return-to-main',CSI+'?1049l',green)
        check('remap-main',regis('R(P)'),green,position)
    main(exercise,suite_name='regis-window-alt-remap-'+query,before_exercise=before,
         font=os.environ['NEMOTERM_TEST_FONT'],profile_values=dict(NemoTabs=0))
