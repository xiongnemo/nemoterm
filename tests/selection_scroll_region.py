"""Track a released visual rectangle when a TUI scrolls part of the screen."""
import ctypes as c
from ctypes import wintypes as w
import json
import os
import struct
import time

from clipboard_test_utils import SavedClipboard, clipboard_text
from hosted_gesture_input import DesktopInput
from native_test_utils import capture_result, root, terminal_host, u, wait_for
from presented_window_capture import PresentedWindowCapture
from protocol_oracle_window import run

CSI = '\x1b['
INK = bytes.fromhex('553322')
ROWS = list(range(8))
# Scroll rows 2..5 inclusive. Negative numbers move the text up.
CASES = [('clip-top',0,2,-1), ('clip-bottom',7,5,1),
         ('split-top',3,1,1), ('split-bottom',4,6,-1),
         ('leave-top',3,1,4), ('leave-bottom',4,6,-4),
         ('keep-inside',3,4,1), ('lose-inside',2,3,-2),
         ('keep-above',1,0,1), ('keep-below',7,6,-1),
         ('span-up',0,7,-2), ('span-down',7,0,2)]


def exercise(hwnd, phase, current):
    renderer = {'gdi':1,'directx':3}[os.environ['RENDERER']]
    u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND,w.LPCWSTR],w.HANDLE
    assert int(u.GetPropW(hwnd,'NemotermRenderer') or 0)==renderer
    pid=w.DWORD(); assert u.GetWindowThreadProcessId(hwnd,c.byref(pid))
    rect=w.RECT(); assert u.GetClientRect(hwnd,c.byref(rect))
    cw,ch=(rect.right-2)//80,(rect.bottom-2)//24
    obs=dict(renderer=renderer,cases={},cell_px=[cw,ch]); clip=SavedClipboard(hwnd); desk=camera=None
    def point(x,y): desk.point(1+x*cw+cw//2,1+y*ch+ch//2)
    try:
        desk=DesktopInput(pid.value,terminal_host(hwnd),hwnd,obs.setdefault('input',{}))
        camera=PresentedWindowCapture(pid.value,hwnd,directx=renderer==3); camera.wait_for_initial_geometry()
        for index,(name,anchor,end,shift) in enumerate(CASES):
            rec=obs['cases'][name]=dict(anchor=anchor,end=end,shift=shift)
            # Labels are outside the drag. A unique green component per case
            # ensures that even an unchanged row cannot satisfy a stale frame.
            def line(i): return f'ROW|{i:02}中!|GUARD{CSI}48;2;{40+i};{80+index};130m  {CSI}0m'
            def sample(stage,ids,selected,check_cols):
                labels=[(bytes([130,80+index,40+i]) if i is not None else bytes(3)).hex() for i in ids]
                expect=[list(range(4,9)) if y in selected else [] for y in ROWS]
                def inspect():
                    bmp=camera.capture(); width,height=struct.unpack_from('<ii',bmp,18)
                    assert (width,-height)==(rect.right,rect.bottom)
                    def pixel(x,y):
                        off=54+4*((2+y*ch)*width+2+x*cw);return bmp[off:off+3]
                    actual_labels=[pixel(15,y).hex() for y in ROWS]
                    actual=[[x for x in range(14) if pixel(x,y)==INK] for y in ROWS]
                    rec[stage]=dict(labels=actual_labels,expected_labels=labels,columns=actual,expected_columns=expect)
                    if labels==actual_labels and (not check_cols or actual==expect): return bmp
                bmp=wait_for(inspect,timeout=5)
                if stage=='scrolled' or index==0:
                    capture_result(rect.right,rect.bottom,bmp[54:],f'scrollback-region-{name}-{stage}.png')
            phase(name+'-draw',CSI+'r'+CSI+'2J'+CSI+'H'+CSI+'?25l'+CSI+'?1002;1006h'+'\x1b]17;#223355\x07\x1b]11;#000000\x07'+'\r\n'.join(map(line,ROWS))+CSI+'3;6r','')
            sample('initial',ROWS,[],True)
            time.sleep(u.GetDoubleClickTime()/1000+.02)
            point(4,anchor);desk.event(0x11,True);desk.event(0x10,True);desk.event(None,True)
            wait_for(lambda:desk.state().capture==hwnd);point(8,end)
            chosen=list(range(min(anchor,end),max(anchor,end)+1));sample('drag',ROWS,chosen,True)
            desk.event(None,False);wait_for(lambda:desk.state().capture!=hwnd);desk.event(0x10,False);desk.event(0x11,False)
            seq=u.GetClipboardSequenceNumber();desk.chord(0x11,0x10,ord('C'));wait_for(lambda:u.GetClipboardSequenceNumber()!=seq)
            rec['copy']=clipboard_text(hwnd);assert rec['copy']=='\r\n'.join(f'{y:02}中!' for y in chosen)
            desk.chord(ord('7'));wire=wait_for(lambda:(v if (v:=current())['hex'].endswith('37') else None));rec['wire']=wire['hex'];assert rec['wire']=='1b5b306e37'
            phase(name+'-scroll',CSI+str(abs(shift))+('S' if shift<0 else 'T'),'')
            ids=ROWS.copy(); mids=ROWS[2:6]; d=abs(shift)
            ids[2:6]=mids[d:]+[None]*d if shift<0 else [None]*d+mids[:-d]
            survivors=[y for y,old in enumerate(ids) if old in chosen]
            # A split source no longer fits one rectangle: remove its highlight;
            # never include an unselected/new blank row to bridge the gap.
            keep=survivors if not survivors or survivors==list(range(survivors[0],survivors[-1]+1)) else []
            sample('scrolled',ids,keep,False)
            rec['clipboard_after']=clipboard_text(hwnd);assert rec['clipboard_after']==rec['copy']
    finally:
        try:
            if camera: obs['capture']=camera.close()
            if desk:desk.restore()
        finally:
            clip.restore(); (root/'research/scrollback-region.json').write_text(json.dumps(obs,indent=2))
    return obs


if __name__=='__main__':
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    run('scrollback-modes-region',[],exercise=exercise,barrier=(CSI+'5n',b'\x1b[0n'),source_reference='Windows rectangular selection over a TUI scroll region',
        font=os.environ['NEMOTERM_TEST_FONT'],profile=dict(WarnOnClose=0,NemoRenderer={'gdi':0,'directx':2}[os.environ['RENDERER']]))
    obs=json.loads((root/'research/scrollback-region.json').read_bytes());assert len(obs['cases'])==len(CASES)
    mismatches=[n for n,r in obs['cases'].items() if r['scrolled']['columns']!=r['scrolled']['expected_columns']]
    assert not mismatches,mismatches
