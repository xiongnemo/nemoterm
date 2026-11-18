"""Only draw if the native terminal advertises ReGIS and reports a usable page."""
import os
import re
from regis_window_smoke import before, context, main, regis, reset, CSI, BORDER, u


def exercise(phase,block):
    blank=dict(x=BORDER,y=BORDER,width=160,height=120,colour='black')
    phase('discover-before-drawing',reset()+CSI+'c'+CSI+'?3;1;0S',[blank])
    raw=bytes.fromhex(context['checks'][-1]['reply_hex'])
    ids,geometry=raw.split(b'c',1)
    assert ids.startswith(b'\x1b[?') and {b'3',b'4'}<=set(ids[3:].split(b';')[1:]), raw
    match=re.fullmatch(rb'\x1b\[\?3;0;(\d+);(\d+)S\x1b\[0n',geometry);assert match,raw
    width,height=map(int,match.groups());assert (width,height)==(800,480)
    x,y=width//8,height//8
    ink=[blank,dict(x=BORDER+x,y=BORDER+y,width=17,height=1,colour='green')]
    phase('draw-using-reported-page',regis(f'S(E)S(M3(R0G100B0))W(I3)P[{x},{y}]V[{x+16},{y}]R(P)',1),ink,expected_reply=f'[{x+16},{y}]\r'.encode())
    assert u.RedrawWindow(context['session']['hwnd'],None,None,0x185)
    phase('read-without-changing-drawing',CSI+'?3;2;0S'+CSI+'?3;3;0S'+CSI+'?3;4;0S'+CSI+'?3;5;0S'+CSI+'?3;1;0S',ink,
          expected_reply=b'\x1b[?3;3S'*3+b'\x1b[?3;2S\x1b[?3;0;800;480S')

if __name__=='__main__':
    main(exercise,suite_name='regis-window-discovery',before_exercise=before,
         font=os.environ['NEMOTERM_TEST_FONT'],profile_values=dict(NemoTabs=0))
