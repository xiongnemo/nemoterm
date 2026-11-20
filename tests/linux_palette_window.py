"""Replay ncurses' actual linux palette commands in a Windows mouse-tracking application."""
import argparse
import ctypes as c
from ctypes import wintypes as w
import json
import os
from pathlib import Path

from clipboard_test_utils import SavedClipboard, clipboard_text, set_clipboard
from hosted_gesture_input import DesktopInput
from native_test_utils import capture_result, root, terminal_host, u, wait_for
from presented_window_capture import PresentedWindowCapture
from protocol_oracle_window import run

CSI='\x1b['; OSC='\x1b]'; ST='\x1b\\'; ACK=b'\x1b[0n'
BASE=[(50+i*6, 200-i*4, 20+i*8) for i in range(16)]
SELECT=(34,51,85)


def test(renderer, style, ref):
    name=f'linux-palette-{renderer}-{style}'; out=root/'research'/name; out.mkdir(exist_ok=False)
    active={'gdi':1,'directx':3}[renderer]; obs=dict(renderer=renderer,style=style,stages={})
    palette=[tuple(row['rgb']) for row in ref['entries']];assert ref['passed'] and len(palette)==16
    legacy=[bytes.fromhex(row['hex']).decode('ascii') for row in ref['entries']]
    modern=[OSC+f'4;{i};#'+bytes(col).hex()+ST for i,col in enumerate(palette)]
    queries=''.join(OSC+f'4;{i};?'+ST for i in range(16))
    # The terminfo output has no BEL or ST. Put an actual printed @ immediately
    # after each command; a later standalone ST lets a broken receiver recover.
    stages=[('legacy-set',legacy,palette),('legacy-reset',[bytes.fromhex(ref['reset']).decode('ascii')],BASE),
            ('modern-set',modern,palette),('modern-reset',[OSC+'104'+ST],BASE),
            ('modern-set-for-reset',modern,palette),('cross-reset',[bytes.fromhex(ref['reset']).decode('ascii')],BASE)]
    # The first six stages are the original before/after comparison. Keep
    # syntax guards separate from the bytes actually produced by ncurses.
    title='R P1123456 is literal title text'
    guards=[OSC+'2;'+title+ST, OSC+'Pz', OSC+'P12x']
    stages.extend([('uppercase-set',[cmd.upper() for cmd in legacy],palette),
                   ('reset-after-uppercase',[bytes.fromhex(ref['reset']).decode('ascii')],BASE),
                   ('literal-and-invalid',guards,BASE)])
    checks=[]
    def exercise(hwnd,phase,current):
        u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
        assert int(u.GetPropW(hwnd,'NemotermRenderer') or 0)==active
        pid=w.DWORD();assert u.GetWindowThreadProcessId(hwnd,c.byref(pid)); rect=w.RECT();assert u.GetClientRect(hwnd,c.byref(rect))
        cw,ch=(rect.right-2)//80,(rect.bottom-2)//24;assert (80*cw+2,24*ch+2)==(rect.right,rect.bottom)
        obs['cell']=[cw,ch];saved=SavedClipboard(hwnd);desk=cam=None
        try:
            desk=DesktopInput(pid.value,terminal_host(hwnd),hwnd,obs.setdefault('input',{}))
            cam=PresentedWindowCapture(pid.value,hwnd,directx=active==3);cam.wait_for_initial_geometry()
            def point(x,y):desk.point(1+x*cw+cw//2,1+y*ch+ch//2)
            def marker(i):return (220,80+i,124)
            def paint_marker(i):
                r,g,b=marker(i);return CSI+'1;31H'+CSI+f'48;2;{r};{g};{b}m '+CSI+'0m'
            def frame(label,i,need_selection=False):
                width=rect.right
                def rgb(b,x,y):
                    idx=54+4*(width*y+x);return tuple(b[idx:idx+3][::-1])
                def read():
                    b=cam.capture();swatches=[rgb(b,2+x*cw,2) for x in range(16)]
                    selected=[x for x in range(10) if rgb(b,2+x*cw,2+2*ch)==SELECT]
                    if rgb(b,2+30*cw,2)==marker(i) and (not need_selection or selected==[3,4,5,6]): return b,swatches,selected
                b,swatches,selected=wait_for(read);capture_result(width,rect.bottom,b[54:],name+'/'+label+'.png')
                # The @ is truecolour white on black regardless of the palette. Count
                # ink in its entire character cell, independent of font antialiasing.
                ink=[x for x in range(17) if any(min(rgb(b,1+x*cw+dx,1+3*ch+dy))>128 for dx in range(cw) for dy in range(ch))]
                return swatches,selected,ink
            def replies(cols):
                return ''.join(OSC+f'4;{i};rgb:'+'/'.join(f'{v:02x}'*2 for v in col)+ST for i,col in enumerate(cols)).encode()
            seed=CSI+'?25l'+CSI+'?1002;1006h'+CSI+'2J'+CSI+'1;1H'+''.join(CSI+f'48;5;{i}m ' for i in range(16))+CSI+'0m'+CSI+'3;3Ha中文z'+paint_marker(0)
            set_clipboard(hwnd,'palette sentinel');phase('scene',seed+CSI+'?1002$p'+CSI+'?1006$p'+queries,b'\x1b[?1002;1$y\x1b[?1006;1$y'+replies(BASE))
            swatches,_,_=frame('before',0);assert swatches==BASE,swatches
            native_base=current()['win32_colorref'];assert len(native_base)==16;obs['native_base']=native_base
            # Win32 numbers colours BGR in the low three index bits. In each
            # COLORREF it stores red in the least significant value byte.
            native_set=[0]*16
            for ansi,(red,green,blue) in enumerate(palette):
                index=(ansi&10)|((ansi&1)<<2)|((ansi&4)>>2)
                native_set[index]=red|(green<<8)|(blue<<16)

            point(3,2);desk.event(0x10,True);desk.event(None,True);wait_for(lambda:desk.state().capture==hwnd);point(6,2)
            frame('selected',0,True);desk.event(None,False);desk.event(0x10,False);wait_for(lambda:desk.state().capture!=hwnd)
            for i,(label,commands,colours) in enumerate(stages,1):
                seq=CSI+'4;1H'+CSI+'2K'+CSI+'38;2;255;255;255;48;2;0;0;0m'+''.join(cmd+'@' for cmd in commands)+ST+CSI+'6n'+queries+paint_marker(i)
                wire=phase(label,seq,None,console_write=style);expected=CSI.encode()+f'4;{1+len(commands)}R'.encode()+replies(colours)
                snapshot=current();assert snapshot['phase']==label
                native_text=''.join(chr(cell[0]) for cell in snapshot['native_row']); native_colours=snapshot['win32_colorref']
                expected_text='@'*len(commands)+' '*(17-len(commands));expected_native=native_set if colours==palette else native_base
                swatches,selected,ink=frame(label,i);clip_seq=u.GetClipboardSequenceNumber();desk.chord(0x11,0x10,ord('C'));desk.chord(ord('8'))
                child=wait_for(lambda:r if (r:=bytes.fromhex(current()['hex'])).endswith(b'8') else None)
                changed=u.GetClipboardSequenceNumber()!=clip_seq;copied=clipboard_text(hwnd)
                passed=dict(replies=wire==expected,swatches=swatches==colours,following_text=ink==list(range(len(commands))),
                            highlight=selected==[3,4,5,6],copy=changed and copied=='中文',input=child==wire+ACK+b'8')
                passed.update(native_text=native_text==expected_text,native_colours=native_colours==expected_native)
                if label=='literal-and-invalid':
                    passed['literal_title']=snapshot['win32_title']==title
                obs['stages'][label]=dict(native_row=snapshot['native_row'],win32_title=snapshot['win32_title'],native_text=native_text,expected_text=expected_text,native_colours=native_colours,expected_native_colours=expected_native,actual=wire.hex(),expected=expected.hex(),colours=swatches,following_text=ink,selected=selected,
                                          clipboard=copied,clipboard_changed=changed,child=child.hex(),checks=passed)
                checks.extend(passed.values())
        finally:
            if cam:cam.close()
            if desk:desk.restore()
            saved.restore()
    # Profiles number normal and bright colours in adjacent pairs, while
    # the wire numbers all eight normal colours before the eight bright ones.
    profile={f'Colour{6+2*(i%8)+i//8}':','.join(map(str,col)) for i,col in enumerate(BASE)}
    profile.update(NemoTabs=1,NemoRenderer=active-1,FontHeight=8,WarnOnClose=0,MouseOverride=1,MouseAutocopy=0,
                   NemoSelectionBackgroundEnabled=1,NemoSelectionBackground=0x223355)
    try:
        run(name,[],exercise=exercise,barrier=(CSI+'5n',ACK),font=os.environ['NEMOTERM_TEST_FONT'],profile=profile,native_row=(0,3,17),
            source_reference='hosted ncurses linux terminfo initc/oc; OSC 4 and screen probes are measured by the Windows fixture')
        obs['passed']=len(checks)==8*len(stages)+1 and all(checks)
    finally:(out/'result.json').write_text(json.dumps(obs,indent=2))
    return obs['passed']


if __name__=='__main__':
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    os.environ['NEMOTERM_TEST_NATIVE_PALETTE']='1'
    p=argparse.ArgumentParser();p.add_argument('reference',type=Path);p.add_argument('renderer',choices=('gdi','directx'));p.add_argument('style',choices=('whole','bytewise'))
    a=p.parse_args();raise SystemExit(not test(a.renderer,a.style,json.loads(a.reference.read_bytes())))
