"""Compare independent mode replies and the actual Windows history position."""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import io
import json
import os
import time
import zipfile
from pathlib import Path

from hosted_gesture_input import DesktopInput
from native_test_utils import root, terminal_host, u, wait_for
from protocol_oracle_window import run
from scrollback_mode_cases import CSI, PROFILES, stages
from selection_history_drag import ScrollInfo


def viewport(hwnd, phase, current, renderer):
    u.GetScrollInfo.argtypes=[w.HWND,c.c_int,c.POINTER(ScrollInfo)]
    u.GetPropW.argtypes=[w.HWND,w.LPCWSTR];u.GetPropW.restype=w.HANDLE
    actual=int(u.GetPropW(hwnd,'NemotermRenderer') or 0)
    assert actual==renderer,actual
    pid=w.DWORD();u.GetWindowThreadProcessId(hwnd,c.byref(pid))
    records=dict(renderer=actual,events=[])
    desk=DesktopInput(pid.value,terminal_host(hwnd),hwnd,records.setdefault('input',{}))
    def position():
        s=ScrollInfo();s.size=c.sizeof(s);s.mask=7
        assert u.GetScrollInfo(hwnd,1,c.byref(s)) and s.page>0
        return (s.pos,s.high-int(s.page)+1)
    try:
        phase('history',CSI+'?25l'+CSI+'?1010h'+'\r\n'.join(f'HISTORY {i:02d}' for i in range(72)),'')
        wait_for(lambda:position()[1]>=48)
        for o,k in PROFILES:
            mode=CSI+'?1010'+('h' if o else 'l')+CSI+'?1011'+('h' if k else 'l')
            for event,enabled in [('output',o),('key',k)]:
                name=f'{int(o)}{int(k)}-{event}';phase('set-'+name,mode,'')
                u.SendMessageW(hwnd,0x115,6,0) # WM_VSCROLL / SB_TOP
                wait_for(lambda:position()[0]==0);top,bottom=position();assert top==0 and bottom>=48
                if event=='output':phase('print-'+name,'X','') # no newline; history length stays fixed
                else:
                    desk.chord(ord('7'));wait_for(lambda:bytes.fromhex(current()['hex'])==b'\x1b[0n7')
                samples=[];start=time.monotonic()
                while True:
                    elapsed=time.monotonic()-start;pos,last=position();samples.append([round(elapsed,3),pos,last])
                    if elapsed>=.55:break
                    time.sleep(.025)
                want=bottom if enabled else top
                records['events'].append(dict(mode=name,expected=want,positions=samples,
                    passed=all(last==bottom and (pos==want or (enabled and t<.3)) for t,pos,last in samples)))
    finally:desk.restore()
    return records


def history_selection(renderer):
    from clipboard_test_utils import SavedClipboard, clipboard_text
    def held(hwnd,phase,current):
        u.GetScrollInfo.argtypes=[w.HWND,c.c_int,c.POINTER(ScrollInfo)]
        u.GetPropW.argtypes=[w.HWND,w.LPCWSTR];u.GetPropW.restype=w.HANDLE
        assert int(u.GetPropW(hwnd,'NemotermRenderer') or 0)==renderer
        u.GetClientRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
        rect=w.RECT();assert u.GetClientRect(hwnd,c.byref(rect))
        cw,ch=(rect.right-2)//80,(rect.bottom-2)//24
        pid=w.DWORD();u.GetWindowThreadProcessId(hwnd,c.byref(pid));record={'cell_pixels':[cw,ch],'renderer':renderer}
        def pos():
            info=ScrollInfo();info.size=c.sizeof(info);info.mask=7;assert u.GetScrollInfo(hwnd,1,c.byref(info))
            return [info.pos,info.high-int(info.page)+1]
        def point(x):return desk.point(1+x*cw+cw//2,1+3*ch+ch//2)
        clip=SavedClipboard(hwnd);desk=None
        try:
            desk=DesktopInput(pid.value,terminal_host(hwnd),hwnd,record.setdefault('input',{}))
            phase('draw',CSI+'?25l'+'\r\n'.join(f'HISTORY {i:02d} 中' for i in range(72))+CSI+'?1010l'+CSI+'?1011h'+CSI+'?1002;1006h','')
            wait_for(lambda:pos()[1]==48);u.SendMessageW(hwnd,0x115,6,0);wait_for(lambda:pos()==[0,48]);record['before']=pos()
            point(0);desk.event(0x10,True);desk.event(None,True);wait_for(lambda:desk.state().capture==hwnd)
            phase('append-while-held','\r\nNEW LIVE OUTPUT','');wait_for(lambda:pos()[1]==49);record['after_output']=pos()
            point(12);desk.event(None,False);wait_for(lambda:desk.state().capture!=hwnd);desk.event(0x10,False)
            seq=u.GetClipboardSequenceNumber();desk.chord(0x11,0x10,ord('C'));wait_for(lambda:u.GetClipboardSequenceNumber()!=seq)
            record['copy']=clipboard_text(hwnd);record['after_copy']=pos();record['before_type_wire']=current()['hex']
            desk.chord(ord('7'));wait_for(lambda:bytes.fromhex(current()['hex']).endswith(b'7'));wait_for(lambda:pos()[0]==49)
            record['after_typing']=pos();record['after_type_wire']=current()['hex']
        finally:
            try:
                if desk:desk.restore()
            finally:
                clip.restore();(root/'research/scrollback-held-history.json').write_text(json.dumps(record,indent=2))
        assert record['before']==[0,48] and record['after_output']==record['after_copy']==[0,49],record
        assert record['copy']=='HISTORY 03 中' and record['before_type_wire']=='1b5b306e' and record['after_type_wire']=='1b5b306e37',record
        return record
    run('scrollback-modes-held',[],barrier=(CSI+'5n',b'\x1b[0n'),exercise=held,font=os.environ['NEMOTERM_TEST_FONT'],
        profile=dict(ScrollOnDisp=1,ScrollOnKey=0,ScrollbackLines=200,ScrollBar=1,NemoRenderer=renderer-1,WarnOnClose=0))


def main():
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    import sys
    if sys.argv[1:]==['--history-selection']:
        history_selection({'gdi':1,'directx':3}[os.environ['RENDERER']]);return
    data=(root/'testdata/upstream/xterm412-scrollback-modes.zip').read_bytes()
    assert hashlib.sha256(data).hexdigest()=='c36021bb9f8a597e6fe8f7eb0fadea0f9a444c75a58d03682006d97130d53895'
    renderer={'gdi':1,'directx':3}[os.environ['RENDERER']];result={};product=Path(os.environ['NEMOTERM_TEST_EXE']);digest=hashlib.sha256(product.read_bytes()).hexdigest()
    with zipfile.ZipFile(io.BytesIO(data)) as ref:
        for o,k in PROFILES:
            tag=f'{int(o)}{int(k)}';name='scrollback-modes-'+tag;src=json.loads(ref.read('scrollback-modes/'+tag+'.json'))['cases'];inputs=stages()
            assert src.keys()==inputs.keys() and all(src[n]['sequence']==s for n,s in inputs.items())
            run(name,[(n,s,None) for n,s in inputs.items()],barrier=(CSI+'5n',b'\x1b[0n'),
                exercise=lambda hwnd,phase,current:viewport(hwnd,phase,current,renderer),font=os.environ['NEMOTERM_TEST_FONT'],
                profile=dict(ScrollOnDisp=int(o),ScrollOnKey=int(k),ScrollbackLines=200,ScrollBar=1,NemoRenderer=renderer-1,WarnOnClose=0))
            v=json.loads((root/'research'/(name+'-observed.json')).read_bytes());assert v['executable_sha256']==digest and v['completed']
            result[tag]=dict(replies={n:v['cases'][n]==row['reply_hex']+'1b5b306e' for n,row in src.items()},
                viewport={event['mode']:event['passed'] for event in v['exercise']['events']})
    (root/'research/scrollback-modes-score.json').write_text(json.dumps(dict(executable_sha256=digest,profiles=result),indent=2))
    assert all(all(check.values()) for tests in result.values() for check in tests.values()),result


if __name__=='__main__':main()
