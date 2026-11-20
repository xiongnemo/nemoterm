"""Check a released rectangle against edits in a different pane of the same rows."""
import ctypes as c
from ctypes import wintypes as w
import json
import os
import struct
import time
import traceback

from clipboard_test_utils import SavedClipboard, clipboard_text, set_clipboard
from hosted_gesture_input import DesktopInput
from native_test_utils import capture_result, root, terminal_host, u, wait_for
from presented_window_capture import PresentedWindowCapture
from protocol_oracle_window import run

CSI='\x1b['
ACK=b'\x1b[0n'
# Byte offsets are never used as screen columns. The rectangle starts on the
# right half of 中 and ends on the left half of 文 (physical columns 7..9).
TEXT='中A文\r\n中B文\r\n中C文'
CASES=[('right-ich',1,16,20,24,2,True),('right-dch',1,16,20,24,-2,True),
       ('left-ich',1,0,2,5,2,True),('left-dch',1,0,2,5,-2,True),
       ('first-right',0,16,20,24,2,True),('last-left',2,0,2,5,-2,True),
       ('other-row',3,8,20,24,2,True),('through-text',1,8,20,24,-2,False),
       ('cut-wide-edge',1,10,20,24,2,False),('move-one-row',1,1,20,24,2,False)]

def trial(renderer):
    mode={'gdi':1,'directx':3}[renderer]; name='scrollback-block-edit-'+renderer
    obs=dict(renderer=renderer,cases={}); checks=[]
    def exercise(hwnd,phase,current):
        u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
        assert int(u.GetPropW(hwnd,'NemotermRenderer') or 0)==mode
        pid=w.DWORD(); assert u.GetWindowThreadProcessId(hwnd,c.byref(pid))
        rect=w.RECT();assert u.GetClientRect(hwnd,c.byref(rect))
        cw,ch=(rect.right-2)//80,(rect.bottom-2)//24;obs['cell']=[cw,ch]
        assert (80*cw+2,24*ch+2)==(rect.right,rect.bottom)
        clip=SavedClipboard(hwnd);desk=cam=None
        try:
            desk=DesktopInput(pid.value,terminal_host(hwnd),hwnd,obs.setdefault('input',{}))
            cam=PresentedWindowCapture(pid.value,hwnd,directx=mode==3);cam.wait_for_initial_geometry()
            def point(x,y):desk.point(1+x*cw+cw//2,1+y*ch+ch//2)
            wanted=[list(range(6,11)) for _ in range(3)];empty=[[],[],[]]
            for i,(label,row,at,marker,end,shift,keep) in enumerate(CASES):
                rec=obs['cases'][label]=dict(edit=[row,at,end,shift],keep=keep,marker_from=marker,marker_to=marker+shift)
                colour=bytes((140,80+i,30)); cup=lambda y,x:f'{CSI}{y+1};{x+1}H'
                def shot(stage,marker_x,expected=None):
                    def read():
                        bmp=cam.capture();width,h=struct.unpack_from('<ii',bmp,18);assert (width,-h)==(rect.right,rect.bottom)
                        def px(x,y):
                            off=54+4*((2+y*ch)*width+2+x*cw);return bmp[off:off+3]
                        marked=[[x for x in range(15) if px(x,y)==b'\x55\x33\x22'] for y in range(3)]
                        markers=[x for x in range(26) if px(x,row)==colour]
                        if markers==[marker_x] and (expected is None or marked==expected):return bmp,marked
                    bmp,marks=wait_for(read,timeout=5);rec[stage]=marks
                    capture_result(rect.right,rect.bottom,bmp[54:],name+'-'+label+'-'+stage+'.png')
                    return marks
                set_clipboard(hwnd,'block-edit sentinel '+label)
                scene=CSI+'?69l'+CSI+'2J'+CSI+'?25l'+CSI+'?1002;1006h'+'\x1b]17;#223355\x07\x1b]11;#000000\x07'
                scene+=''.join(cup(y,5)+'a中'+letter+'文z' for y,letter in enumerate('ABCD'))
                scene+=cup(row,marker)+f'{CSI}48;2;30;{80+i};140m '+CSI+'0m'+CSI+'?69h'+f'{CSI}1;{end}s'
                phase(label+'-seed',scene+CSI+'?1002$p'+CSI+'?1006$p',b'\x1b[?1002;1$y\x1b[?1006;1$y');shot('seed',marker,empty)
                time.sleep(u.GetDoubleClickTime()/1000+.02)
                reverse=i%2; p,q=((9,2),(7,0)) if reverse else ((7,0),(9,2))
                point(*p);desk.event(0x10,True);desk.event(0x11,True);desk.event(None,True)
                wait_for(lambda:desk.state().capture==hwnd);point(*q);shot('drag',marker,wanted)
                desk.event(None,False);wait_for(lambda:desk.state().capture!=hwnd);desk.event(0x11,False);desk.event(0x10,False)
                seq=u.GetClipboardSequenceNumber();desk.chord(0x11,0x10,ord('C'));wait_for(lambda:u.GetClipboardSequenceNumber()!=seq)
                rec['initial_copy']=clipboard_text(hwnd);assert rec['initial_copy']==TEXT
                phase(label+'-edit',cup(row,at)+CSI+str(abs(shift))+('@' if shift>0 else 'P'),b'')
                marks=shot('edited',marker+shift);rec['clipboard_after_edit']=clipboard_text(hwnd)
                point(15,4);seq=u.GetClipboardSequenceNumber();desk.chord('right');desk.chord(ord('8'))
                wire=wait_for(lambda:v if (v:=bytes.fromhex(current()['hex'])).endswith(b'8') else None)
                rec.update(right_changed=u.GetClipboardSequenceNumber()!=seq,right_text=clipboard_text(hwnd),wire=wire.hex())
                target=ACK+(b'' if keep else b'\x1b[<2;16;5M\x1b[<2;16;5m')+b'8'
                rec['passed']=marks==(wanted if keep else empty) and rec['right_changed']==keep and rec['right_text']==rec['clipboard_after_edit']==TEXT and wire==target
                checks.append(rec['passed'])
        finally:
            if cam:cam.close()
            if desk:desk.restore()
            clip.restore()
    try:
        run(name,[],exercise=exercise,barrier=(CSI+'5n',ACK),font=os.environ['NEMOTERM_TEST_FONT'],source_reference='visible Windows rectangle and actual mouse/clipboard recipient',
            profile=dict(NemoTabs=1,NemoRenderer=mode-1,FontHeight=8,WarnOnClose=0,MouseOverride=1,MouseAutocopy=0))
    except Exception:obs['error']=traceback.format_exc()
    obs['passed']='error' not in obs and len(checks)==len(CASES) and all(checks)
    (root/'research'/(name+'.json')).write_text(json.dumps(obs,indent=2),encoding='utf-8');return obs['passed']

if __name__=='__main__':
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    raise SystemExit(not trial(os.environ['RENDERER']))
