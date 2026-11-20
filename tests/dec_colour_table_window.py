"""Read and replay VT525 palette reports through an actual Windows console child."""
import argparse
from hashlib import sha256
import json
import os

from native_test_utils import w, u, root
from protocol_oracle_window import run

CSI, DCS, ST = '\x1b[', '\x1bP', '\x1b\\'
# The first 16 entries and expected results are data from Microsoft's VT525
# hardware comparison (microsoft/terminal PR 17708, ColorTableReportTests).
PALETTE = [(0,0,0),(204,36,36),(51,204,51),(204,204,51),(51,51,204),(204,51,204),(51,204,204),
           (120,120,120),(69,69,69),(255,0,0),(0,255,0),(255,255,0),(0,0,255),(255,0,255),(0,255,255),(255,255,255)]
HLS = [(0,0,0),(120,47,70),(240,50,60),(180,50,60),(0,50,60),(60,50,60),(300,50,60),
       (0,47,0),(0,27,0),(120,50,100),(240,50,100),(180,50,100),(0,50,100),(60,50,100),(300,50,100),(0,100,0)]
RGB = [(0,0,0),(80,14,14),(20,80,20),(80,80,20),(20,20,80),(80,20,80),(20,80,80),
       (47,47,47),(27,27,27),(100,0,0),(0,100,0),(100,100,0),(0,0,100),(100,0,100),(0,100,100),(100,100,100)]


def table(model, entries):
    return DCS+'2$s'+'/'.join(';'.join(map(str,(i,model,*color))) for i,color in enumerate(entries))+ST


def osc_read(index): return f'\x1b]4;{index};?\x07'

def osc_value(index, triple): return f'\x1b]4;{index};rgb:'+('/'.join(f'{c:02x}{c:02x}' for c in triple))+'\x07'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('renderer',choices=('gdi','directx'));p.add_argument('style',choices=('whole','bytewise'));a=p.parse_args()
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    name=f'dec-colour-table-{a.renderer}-{a.style}'; rows={}; result=root/'research'/(name+'-checks.json')
    def exercise(hwnd, phase, current):
        u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
        assert int(u.GetPropW(hwnd,'NemotermRenderer') or 0)=={'gdi':1,'directx':3}[a.renderer]
        def record(key, seq, want, style=None):
            wire=phase(key,seq,None,console_write=style).decode('ascii')
            rows[key]=dict(passed=wire==want,expected_bytes=len(want),received_bytes=len(wire),
                expected_sha256=sha256(want.encode()).hexdigest(),received_sha256=sha256(wire.encode()).hexdigest())
            result.write_text(json.dumps(rows,indent=2),encoding='utf8');return wire
        palette=PALETTE+[(0,0,0)]*240
        seed=''.join(f'\x1b]4;{i};#{r:02x}{g:02x}{b:02x}\x07' for i,(r,g,b) in enumerate(palette))
        record('seed-last-and-first',seed+osc_read(1)+osc_read(255),osc_value(1,PALETTE[1])+osc_value(255,(0,0,0)))
        hls,rgb=(table(model,arr+[(0,0,0)]*240) for model,arr in [(1,HLS),(2,RGB)])
        record('read-hls',CSI+'2;1$u',hls,a.style); actual=record('read-rgb',CSI+'2;2$u',rgb,a.style)
        record('unsupported',CSI+'1$u'+CSI+'2$u'+CSI+'2;0$u'+CSI+'2;3$u','',a.style)
        mutate=DCS+'2$s0;2;0;100;0/255;1;120;50;100'+ST
        record('restore-two-models',mutate+osc_read(0)+osc_read(255),osc_value(0,(0,255,0))+osc_value(255,(255,0,0)),a.style)
        # Replay the application's own saved table; the query/restore format is percent-based.
        # A baseline with no reply must still carry the restore probe through the window.
        record('independent-restore-sentinel','\x1b]4;0;#112233;1;#445566;255;#778899\x07'+osc_read(0)+osc_read(1)+osc_read(255),
               osc_value(0,(17,34,51))+osc_value(1,(68,85,102))+osc_value(255,(119,136,153)))
        record('restore-full-table',(actual or rgb)+osc_read(0)+osc_read(1)+osc_read(255),
               osc_value(0,(0,0,0))+osc_value(1,(204,36,36))+osc_value(255,(0,0,0)),a.style)
        record('first-last-and-duplicate',DCS+'2$s0;2;100;0;0/255;2;99;51;1/0;1;0;50;100'+ST+osc_read(0)+osc_read(255),
               osc_value(0,(0,0,255))+osc_value(255,(252,130,3)),a.style)
        record('cancel-after-complete-entry',DCS+'2$s0;2;0;100;0/255;2;100;0;100\x18'+osc_read(0)+osc_read(255),
               osc_value(0,(0,0,255))+osc_value(255,(252,130,3)),a.style)
        record('invalid-entries-do-not-escape',DCS+'2$s256;2;100;100;100/0;2;9;8/0;9;0;0;0/0;2;100;0;999999999999999999999/254;2;0;100;0'+ST+osc_read(0)+osc_read(254),
               osc_value(0,(0,0,255))+osc_value(254,(0,255,0)),a.style)
        # A light theme can exceed one 4 KiB input buffer even with exactly 256 registers.
        # Mutate a swatch through OSC before replaying the actual reply to catch a no-op restore.
        white = table(2,[(100,100,100)]*256); assert len(white)>4096
        actual=record('report-over-4k',white+CSI+'2;2$u',white,a.style)
        record('restore-over-4k','\x1b]4;255;#000000\x07'+(actual or white)+osc_read(255),osc_value(255,(255,255,255)),a.style)
        return dict(checks=rows)
    run(name,(),exercise=exercise,profile=dict(NemoRenderer={'gdi':0,'directx':2}[a.renderer],WarnOnClose=0),
        font='SarasaTermSC Nerd Light',barrier=(CSI+'5n',b'\x1b[0n'),source_reference='VT525 colour table values in microsoft/terminal PR 17708')
    print({k:v['passed'] for k,v in rows.items()});return all(r['passed'] for r in rows.values())


if __name__=='__main__': raise SystemExit(not main())
