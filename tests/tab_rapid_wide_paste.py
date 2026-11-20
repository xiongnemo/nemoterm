"""Rapidly reselect wide glyphs on the alternate screen; count the exact application paste bytes."""
import io
import json
import os
import time
from PIL import Image
from clipboard_test_utils import SavedClipboard, clipboard_text
from hosted_gesture_input import DesktopInput
from native_test_utils import c, w, u, root, terminal_host, wait_for
from presented_window_capture import PresentedWindowCapture
from protocol_oracle_window import run

ACK = b'\x1b[0n'
ALT = b'\x1b[?47;1$y'
TEXT = '|A中文YZ|'


def wrapped(text):
    return b'\x1b[200~' + text.encode('utf-8') + b'\x1b[201~'


def exercise(renderer, paste, out):
    def check(hwnd, phase, current):
        u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND,w.LPCWSTR], w.HANDLE
        assert u.GetPropW(hwnd,'NemotermRenderer') == renderer+1
        owner=w.DWORD(); assert u.GetWindowThreadProcessId(hwnd,c.byref(owner))
        host=terminal_host(hwnd); assert host!=hwnd
        record=dict(copy_paste=paste,renderer=renderer,font=os.environ['NEMOTERM_TEST_FONT'],pid=owner.value)
        desk=DesktopInput(owner.value,host,hwnd,record.setdefault('desktop',{}))
        saved=SavedClipboard(hwnd); capture=None
        try:
            r=w.RECT(); assert u.GetClientRect(hwnd,c.byref(r)); cw,dx=divmod(r.right-2,80); ch,dy=divmod(r.bottom-2,24)
            assert not(dx or dy) and min(cw,ch)>0; y=6
            capture=PresentedWindowCapture(owner.value,hwnd,raise_window=False)
            phase('receive','\x1b[?1049h\x1b[?25l\x1b[2J\x1b[7;1H'+TEXT+'\x1b[9;1H'+TEXT+
                  '\x1b[?2004h\x1b[?1002;1006h\x1b[?47$p',ALT)
            def pic(): return Image.open(io.BytesIO(capture.capture())).convert('RGB')
            def cell(im,x,row): return im.crop((1+x*cw,1+row*ch,1+(x+1)*cw,1+(row+1)*ch)).tobytes()
            def crop(im): return im.crop((1,1+y*ch,1+9*cw,1+(y+1)*ch))
            def ready():
                im=pic()
                return im if all(cell(im,x,y)==cell(im,x,y+2) and len(set(cell(im,x,y)))>1 for x in (1,2,4,6,7)) else None
            source=wait_for(ready);crop(source).save(out/'source.png')
            def aim(x): desk.point(1+x*cw+cw//2,1+y*ch+ch//2)
            def down():
                aim(2);desk.event(0x10,True);desk.event(None,True);wait_for(lambda:desk.state().capture==hwnd)
            def up(x):
                aim(x);desk.event(None,False);wait_for(lambda:desk.state().capture!=hwnd);desk.event(0x10,False)
            start=time.monotonic_ns();down();up(5)
            seq=u.GetClipboardSequenceNumber();desk.chord('right');wait_for(lambda:u.GetClipboardSequenceNumber()!=seq)
            record['right_copy']=clipboard_text(hwnd);assert record['right_copy']=='中文',record
            down();record['interval_upper_ms']=(time.monotonic_ns()-start)/1e6;record['double_click_ms']=u.GetDoubleClickTime()
            assert record['interval_upper_ms']<record['double_click_ms'],record
            up(6)
            def highlighted():
                im=pic();hits=[x for x in range(9) if cell(im,x,y)!=cell(source,x,y)]
                record['highlight']=hits
                return im if hits==[2,3,4,5,6] else None
            crop(wait_for(highlighted)).save(out/'selected.png')
            seq=u.GetClipboardSequenceNumber();desk.chord(0x11,0x10,ord('C'));wait_for(lambda:u.GetClipboardSequenceNumber()!=seq)
            record['shortcut_copy']=clipboard_text(hwnd);assert record['shortcut_copy']=='中文Y',record
            desk.chord(0x11,0x10,ord('V'));desk.chord(ord('Z'))
            wait_for(lambda: bytes.fromhex(current()['hex']).endswith(b'z'));desk.chord(ord('Y'))
            actual=wait_for(lambda:q if (q:=bytes.fromhex(current()['hex'])).endswith(b'zy') else None)
            expected=ALT+ACK+(wrapped('中文') if paste else b'')+wrapped('中文Y')+b'zy'
            record.update(wire=actual.hex(),expected=expected.hex(),cell=[cw,ch],completed=actual==expected)
            assert actual==expected,record
            return record
        finally:
            (out/'gesture.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
            if capture: capture.close()
            try: desk.restore()
            finally: saved.restore()
    return check


if __name__=='__main__':
    os.environ['NEMOTERM_TEST_INPUT_CP']='65001'; failures=[]
    for renderer,label in ((0,'gdi'),(2,'directx')):
        for paste in (False,True):
            name='wide-rapid-'+label+('-copy-paste' if paste else '-copy')
            out=root/'research'/'tab-hover-native'/name;out.mkdir(parents=True,exist_ok=True)
            profile=dict(NemoTabs=1,NemoRenderer=renderer,NemoTabSide=3,ScrollBar=0,WindowBorder=1,WarnOnClose=0,FontHeight=10)
            if paste:profile['RightClickCopyAndPaste']=1  # absent in the default-profile control
            try: run(name,[],exercise=exercise(renderer,paste,out),barrier=('\x1b[5n',ACK),
                 source_reference='Hosted mouse, displayed cells and ordered child bytes',profile=profile,font=os.environ['NEMOTERM_TEST_FONT'])
            except Exception as err: failures.append((name,repr(err)));print(name,repr(err),flush=True)
    if failures: raise SystemExit('Failed: '+str(failures))
