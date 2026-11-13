"""Exact palette/title-stack replies and renderer invalidation in an owned job."""
import argparse
from palette_stack_oracle_cases import CASES
from protocol_oracle_window import run
from native_test_utils import (capture, hashlib, terminal_host, u, k, c, w,
                              wait_for, time, memory_sample, os)
from gpu_capture import OwnedGPUCapture

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--renderer',choices=('gdi','directx','opengl'),default='gdi')
args=parser.parse_args()
requested={'gdi':0,'opengl':1,'directx':2}[args.renderer]
CSI='\x1b['
barrier=(CSI+'>q',b'\x1bP>|Nemoterm(PuTTY 0.85)\x1b\\')
u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE


def exercise(hwnd,phase,current):
    pid=w.DWORD();u.GetWindowThreadProcessId(hwnd,c.byref(pid))
    handle=k.OpenProcess(0x410,False,pid.value);assert handle
    active=int(u.GetPropW(hwnd,'NemotermRenderer') or 0)
    assert active in (1,2,3),active
    if requested==0:assert active==1
    if requested==1 and os.environ.get('NEMOTERM_REQUIRE_OPENGL')=='1':assert active==2
    if requested==2 and os.environ.get('NEMOTERM_REQUIRE_DIRECTX')=='1':assert active==3
    gpu=None
    evidence=dict(actual_renderer=active,pixel_checks=[],memory_samples=[],memory_instrumented=active!=1)
    try:
        if active!=1:gpu=OwnedGPUCapture(pid.value,hwnd)
        def image():return gpu.capture(return_pixels=True) if gpu else capture(hwnd,return_pixels=True)
        def remember(name):
            time.sleep(.08)
            pixels=image()
            evidence['pixel_checks'].append(dict(name=name,sha256=hashlib.sha256(pixels).hexdigest()))
            evidence['memory_samples'].append(memory_sample(handle))
            return pixels
        def matches(expected):
            return wait_for(lambda:image()==expected)

        scene=('\x1bc'+CSI+'?25l\x1b]10;#ffffff;#000000;#ffffff\x07'+
               '\x1b]4;1;#ff0000;2;#0000ff\x07'+CSI+'2J'+CSI+'2;3H'+
               CSI+'31mPalette 中文 e\u0301'+CSI+'0m'+CSI+'4;3H'+
               CSI+'4:3;58;5;1mUNDERLINE'+CSI+'0m'+CSI+'6;3HDEFAULT TEXT'+
               CSI+'8;3H\x1bP0;1q"1;1;40;24#1;2;0;100;0#1'+('!40~-')*4+'\x1b\\')
        phase('baseline',scene,'');baseline=remember('baseline')
        phase('save-and-change',CSI+'1#P\x1b]4;1;#0000ff\x07\x1b]10;#00ff00;#101020\x07','')
        changed=remember('changed');assert changed!=baseline
        phase('restore-without-redrawing-text',CSI+'1#Q','')
        matches(baseline);assert remember('restored')==baseline

        phase('freeze-palette',CSI+'1#P'+CSI+'?2026h\x1b]4;1;#0000ff\x07','')
        assert remember('frozen')==baseline
        phase('commit-palette',CSI+'?2026l','')
        assert remember('committed')!=baseline
        phase('restore-after-sync',CSI+'1#Q','')
        matches(baseline)

        before=[current()['columns'],current()['rows']]
        assert u.MoveWindow(terminal_host(hwnd),50,50,780,540,True)
        wait_for(lambda:[current()['columns'],current()['rows']]!=before)
        phase('resized-scene',scene,'');resized=remember('resized')
        phase('resized-change',CSI+'10#P\x1b]4;1;#0000ff\x07','')
        assert remember('resized-changed')!=resized
        phase('resized-restore',CSI+'10#Q','');matches(resized)
        assert remember('resized-restored')==resized
        evidence['resized_grid']=[current()['columns'],current()['rows']]

        for i in range(20):
            phase('bounded-cycles-'+str(i),(CSI+'1#P'+CSI+'1#Q')*50,'')
            evidence['memory_samples'].append(memory_sample(handle))
        assert image()==resized
        evidence['repeated_save_restore']=1000
        evidence['peak_private_ws']=max(s['private_ws'] for s in evidence['memory_samples'])
        evidence['peak_total_ws']=max(s['total_ws'] for s in evidence['memory_samples'])
        if active==1:assert evidence['peak_private_ws']<20_000_000,evidence
        if gpu:gpu.capture(f'palette-stack-{args.renderer}-window.png')
        else:capture(hwnd,f'palette-stack-{args.renderer}-window.png')
        return evidence
    finally:
        if gpu:gpu.close()
        k.CloseHandle(handle)


run('palette-stack-'+args.renderer,CASES,exercise=exercise,barrier=barrier,
    profile=dict(NemoRenderer=requested,RemoteQTitleAction=2,WarnOnClose=0),
    font=os.environ.get('NEMOTERM_TEST_FONT','Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light'))
