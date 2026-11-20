"""Physical Shift selections while the TUI clears saved lines (ED/DECSED 3)."""
import ctypes as c
from ctypes import wintypes as w
import json
import os
import time
import traceback

from clipboard_test_utils import SavedClipboard, clipboard_text, set_clipboard
from hosted_gesture_input import DesktopInput
from native_test_utils import capture_result, root, terminal_host, u, wait_for
from presented_window_capture import PresentedWindowCapture
from protocol_oracle_window import run
from selection_history_drag import ScrollInfo
from selection_history_eviction import line, INK

CSI = '\x1b['
ACK = b'\x1b[0n'
# view, gesture stage at clear, clear request, policy denies, reverse rectangle.
CASES = [
    ('history','press','3J',False,False), ('history','drag','?3J',False,True),
    ('history','released','3J',False,False), ('live','press','?3J',False,True),
    ('live','released','3J',False,False), ('partway','drag','3J',False,True),
    ('history','press','3J',True,False), ('history','released','?3J',True,True),
    ('history','drag','menu',True,True), ('partway','drag','menu',True,True),
]


def replay(renderer, view, stage, op, denied, reverse):
    menu=op=='menu'; blocked=denied and not menu
    case=f'{view}-{stage}-{int(denied)}'+('-menu' if menu else ''); name=f'scrollback-clear-{renderer}-{case}'
    font=os.environ['NEMOTERM_TEST_FONT']; keep=view!='history' or blocked
    rec=dict(view=view,stage=stage,request=op,denied=denied,rectangle=reverse,renderer=renderer,checks={})
    def exercise(hwnd,phase,current):
        host=terminal_host(hwnd);assert host!=hwnd
        pid=w.DWORD();u.GetWindowThreadProcessId(hwnd,c.byref(pid))
        u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
        assert int(u.GetPropW(hwnd,'NemotermRenderer') or 0)=={'gdi':1,'directx':3}[renderer]
        u.GetScrollInfo.argtypes=[w.HWND,c.c_int,c.POINTER(ScrollInfo)]
        def pos():
            info=ScrollInfo();info.size=c.sizeof(info);info.mask=7
            assert u.GetScrollInfo(hwnd,1,c.byref(info));return [info.pos,info.high-int(info.page)+1]
        rect=w.RECT();assert u.GetClientRect(hwnd,c.byref(rect));width,height=rect.right,rect.bottom
        cw,ch=(width-2)//80,(height-2)//24;rec['cell']=[cw,ch]
        def point(x,y):desk.point(1+x*cw+cw//2,1+y*ch+ch//2)
        def frame(label,first,selected,y):
            until=time.monotonic()+3;previous=None;since=time.monotonic()
            while True:
                bmp=camera.capture();pixels=bmp[54:]
                def colour(x,yy):
                    offset=4*((2+yy*ch)*width+2+x*cw);return pixels[offset:offset+3]
                observed=[colour(15,yy) for yy in range(7)]
                marked=[[x for x in range(12) if colour(x,yy)==INK] for yy in range(7)]
                wanted=[[4,5,6,7,8] if selected and yy==y else [] for yy in range(7)]
                success=(observed==[bytes([130,90,40+first+yy]) for yy in range(7)] and marked==wanted)
                state=observed,marked;now=time.monotonic()
                if state!=previous:previous=state;since=now
                if (success and now-since>=.12) or now>=until:break
                time.sleep(.025)
            rec[label]=dict(row_colours=[v.hex() for v in observed],highlight=marked,position=pos(),expected_first=first)
            rec['checks'][label]=success;capture_result(width,height,pixels,name+'-'+label+'.png')
        def fence(key):
            desk.chord(ord(key));return wait_for(lambda:wire if (wire:=bytes.fromhex(current()['hex'])).endswith(key.encode()) else None)
        def copy(label,keys,key,expected,expected_input):
            phase(label,'',b'');seq=u.GetClipboardSequenceNumber();desk.chord(*keys);wire=fence(key)
            changed=u.GetClipboardSequenceNumber()!=seq;value=clipboard_text(hwnd)
            rec[label]=dict(changed=changed,text=value,wire=wire.hex(),expected_text=expected)
            rec['checks'][label]=(changed==(expected is not None) and value==(expected if expected is not None else baseline) and wire==ACK+expected_input+key.encode())
        clip=SavedClipboard(hwnd);camera=desk=None
        try:
            desk=DesktopInput(pid.value,host,hwnd,rec.setdefault('input',{}));camera=PresentedWindowCapture(pid.value,hwnd,directx=renderer=='directx');camera.wait_for_initial_geometry()
            scene=(CSI+'?25l'+CSI+'?1010l'+CSI+'?1011l'+CSI+'?1002;1006h'+'\x1b]17;#223355\x07'+'\r\n'.join(line(i) for i in range(56)))
            phase('seed',scene+CSI+'?1002$p'+CSI+'?1006$p',b'\x1b[?1002;1$y\x1b[?1006;1$y');wait_for(lambda:pos()==[32,32])
            if view=='history':u.SendMessageW(hwnd,0x115,6,0)
            if view=='partway':u.SendMessageW(hwnd,0x115,0,0) # One live row above the usual viewport
            first={'live':32,'history':0,'partway':31}[view];wait_for(lambda:pos()==[first,32]);frame('initial',first,False,3);assert rec['checks']['initial']
            phase('input','',b'')
            baseline='clear history clipboard sentinel';set_clipboard(hwnd,baseline);start,end=(8,4) if reverse else (4,8)
            y=3;oldtext=f'{first+y:02d}中!';point(start,y);desk.event(0x10,True)
            if reverse:desk.event(0x11,True)
            desk.event(None,True);wait_for(lambda:desk.state().capture==hwnd)
            if stage!='press':point(end,y)
            if stage=='released':desk.event(None,False);wait_for(lambda:desk.state().capture!=hwnd)
            if reverse:desk.event(0x11,False)
            desk.event(0x10,False);frame('before_clear',first,stage!='press',y);assert rec['checks']['before_clear']
            if stage=='released':
                copy('previous_copy',(0x11,0x10,ord('C')),'4',oldtext,b'');baseline=oldtext
            after=first if blocked else 32;newy=y+first-after if keep else y
            target_pos=[first,32] if blocked else [0,0]
            queued=stage=='drag' and not menu
            if menu:
                # Dispatch the actual Clear Scrollback menu command to the terminal
                # HWND while capture remains held. Opening a menu would steal it.
                u.SendMessageW(hwnd,0x111,0x0060,0)
            elif queued:
                def release_pending(written):
                    assert written['hex']=='' and desk.state().capture==hwnd
                    frame('while_queued',first,True,y)
                    waiting=current();rec['queued_wire']=waiting['hex']
                    rec['checks']['held_until_release']=(waiting['phase']=='clear' and not waiting['hex'] and pos()==[first,32] and desk.state().capture==hwnd)
                    desk.event(None,False);wait_for(lambda:desk.state().capture!=hwnd)
                phase('clear',CSI+op,b'',after_write=release_pending)
            else:
                phase('clear',CSI+op,b'')
            wait_for(lambda:pos()==target_pos)
            frame('after_clear',after,keep and stage!='press',newy)
            if stage!='released' and not queued:
                assert desk.state().capture==hwnd
                if menu and not keep:point(end+1,newy)  # Actual motion after losing the selected line
                point(end,newy);desk.event(None,False);wait_for(lambda:desk.state().capture!=hwnd)
            rec['gesture_wire']=fence('7').hex();rec['checks']['ownership']=rec['gesture_wire']==(ACK+b'7').hex()
            frame('after_release',after,keep,newy)
            if keep:copy('copy',(0x11,0x10,ord('C')),'8',oldtext,b'')
            point(end,newy);raw=b'' if keep else f'{CSI}<2;{end+1};{newy+1}M{CSI}<2;{end+1};{newy+1}m'.encode()
            copy('right',('right',),'9',oldtext if keep else None,raw)
            # A cancelled local gesture must not swallow the next independent selection.
            phase('fresh','',b'');point(4,5);desk.event(0x10,True);desk.event(None,True);wait_for(lambda:desk.state().capture==hwnd)
            point(8,5);desk.event(None,False);wait_for(lambda:desk.state().capture!=hwnd);desk.event(0x10,False)
            rec['fresh_wire']=fence('6').hex();rec['checks']['fresh_ownership']=rec['fresh_wire']==(ACK+b'6').hex()
            copy('fresh_copy',(0x11,0x10,ord('C')),'5',f'{after+5:02d}中!',b'')
        finally:
            try:
                if camera:camera.close()
                if desk:desk.restore()
            finally:clip.restore()
    try:
        run(name,[],exercise=exercise,barrier=(CSI+'5n',ACK),font=font,source_reference='Windows history, presented pixels, clipboard and child input',
            profile=dict(NemoTabs=1,NemoRenderer={'gdi':0,'directx':2}[renderer],FontHeight=8,WarnOnClose=0,MouseOverride=1,MouseAutocopy=0,
                         NoRemoteClearScroll=int(denied),ScrollbackLines=32,ScrollBar=1,ScrollOnDisp=0,ScrollOnKey=0))
    except Exception:rec['error']=traceback.format_exc()
    rec['passed']='error' not in rec and bool(rec['checks']) and all(rec['checks'].values());(root/'research'/(name+'-result.json')).write_text(json.dumps(rec,indent=2),encoding='utf-8');return rec['passed']


if __name__=='__main__':
    if os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise SystemExit('Requires a GitHub hosted Windows desktop')
    outcomes=[replay(os.environ['RENDERER'],*case) for case in CASES];raise SystemExit(not all(outcomes))
