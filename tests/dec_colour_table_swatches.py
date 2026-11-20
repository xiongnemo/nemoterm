"""Measure already-painted indexed cells and Win32 console colours before/after DECCTR restore."""
import argparse
import ctypes as c
import json
import os
from native_test_utils import w,u,root,wait_for,capture_result
from presented_window_capture import PresentedWindowCapture
from protocol_oracle_window import run
from dec_colour_table_window import CSI,DCS,ST,osc_read,osc_value


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('renderer',choices=('gdi','directx'));parser.add_argument('style',choices=('whole','bytewise'));args=parser.parse_args()
    assert os.environ['RUNNER_ENVIRONMENT']=='github-hosted';os.environ['NEMOTERM_TEST_NATIVE_PALETTE']='1'
    name='dec-swatch-'+args.renderer+'-'+args.style;out=root/'research'/name;out.mkdir(exist_ok=False)
    record=dict(stages={}); active={'gdi':1,'directx':3}[args.renderer]; ids=(0,1,254,255)
    seed=[(18,52,86),(137,42,69),(39,101,73),(114,62,128)]
    def exercise(hwnd,phase,current):
        u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
        assert int(u.GetPropW(hwnd,'NemotermRenderer') or 0)==active; pid=w.DWORD();assert u.GetWindowThreadProcessId(hwnd,c.byref(pid))
        rect=w.RECT();assert u.GetClientRect(hwnd,c.byref(rect));ww,hh=rect.right,rect.bottom;cw,ch=(ww-2)//80,(hh-2)//24;assert (80*cw+2,24*ch+2)==(ww,hh)
        record.update(cell=[cw,ch],pid=pid.value,renderer=active);cam=PresentedWindowCapture(pid.value,hwnd,directx=active==3)
        try:
            cam.wait_for_initial_geometry();
            def stage(label,seq,expected):
                marker=(21,91+len(record['stages'])*30,151)
                bar=CSI+'2;10H'+CSI+'48;2;%d;%d;%dm '%marker+CSI+'0m'
                reply=phase(label,seq+bar+''.join(osc_read(i) for i in ids),None,console_write=args.style)
                def frame():
                    b=cam.capture()
                    def px(x,y):
                        k=54+4*(y*ww+x);return tuple(b[k:k+3][::-1])
                    if px(2+9*cw,2+ch)==marker:return b,[px(2+i*cw,2) for i in range(len(ids))]
                frame_bytes,colours=wait_for(frame);capture_result(ww,hh,frame_bytes[54:],name+'/'+label+'.png')
                # The native 16-entry API uses BGR numbering (ANSI black=0, red=4).
                native=current()['win32_colorref'];local=[(native[i]&255,(native[i]>>8)&255,(native[i]>>16)&255) for i in (0,4)]
                row=dict(ids=ids,expected=expected,presented=colours,win32_first_two=local,osc_reply=reply.hex(),
                    protocol_ok=reply==''.join(osc_value(i,v) for i,v in zip(ids,expected)).encode(),
                    painted_ok=colours==expected,native_ok=local==expected[:2]);record['stages'][label]=row
                (out/'stages.json').write_text(json.dumps(record,indent=2),encoding='utf8')
            commands=''.join(f'\x1b]4;{i};#{bytes(v).hex()}\x07' for i,v in zip(ids,seed))
            # Only this stage prints the four samples. Subsequent stages edit the palette
            # and move a separate true-colour progress marker on a different row.
            swatches=CSI+'?25l'+CSI+'H'+''.join(CSI+f'48;5;{i}m ' for i in ids)+CSI+'0m'
            stage('initial',commands+swatches,seed)
            changed=[(255,0,0),(0,0,255),(0,255,0),(252,130,3)]
            stage('restored',DCS+'2$s0;1;120;50;100/1;1;0;50;100/254;2;0;100;0/255;2;99;51;1'+ST,changed)
            stage('cancelled',DCS+'2$s0;2;100;100;100/1;2;100;100;100\x18',changed)
            stage('subset',DCS+'2$s254;2;100;100;0'+ST,changed[:2]+[(255,255,0),changed[3]])
        finally:
            cam.close();record['capture']=cam.record;(out/'stages.json').write_text(json.dumps(record,indent=2),encoding='utf8')
        return record
    run(name,(),exercise=exercise,profile=dict(NemoRenderer=active-1,WarnOnClose=0),font='SarasaTermSC Nerd Light',barrier=(CSI+'5n',b'\x1b[0n'),source_reference='direct window surface and GetConsoleScreenBufferInfoEx')
    return len(record['stages'])==4 and all(all(s[k] for k in ('protocol_ok','painted_ok','native_ok')) for s in record['stages'].values())


if __name__=='__main__':raise SystemExit(not main())
