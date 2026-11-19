"""Actual tab-strip pixels after a console child writes OSC 9;4. Hosted Windows only."""
import json
import os
import struct
import time
from native_test_utils import c, w, u, root, terminal_host, capture_result, wait_for
from presented_window_capture import PresentedWindowCapture
from protocol_oracle_window import run

# Microsoft Terminal's TerminalApiTest::SetTaskbarProgress plus lifecycle controls.
CASES = [ ('normal', '4;1;50', 1, 50), ('clear', '4;0;0', 0, 0),
          ('unknown-state', '4;5;50', 0, 0), ('clamp', '4;1;200', 1, 100),
          ('ignore-extra', '4;1;80;extra', 1, 80), ('error-keep', '4;2;', 2, 80),
          ('busy', '4;3;75', 3, 80), ('pause-previous', '4;4', 4, 80),
          ('bad-value', '4;1;25x', 4, 80), ('other-osc9', '9;C:\\work', 4, 80),
          ('clear-value', '4;0;50', 0, 0), ('error-from-zero', '4;2;', 2, 10),
          ('paused-value', '4;4;65', 4, 65), ('normal-zero', '4;1;0', 1, 0),
          ('pause-from-zero', '4;4;0', 4, 10), ('hard-reset', None, 0, 0) ]
# Colour is in DIB byte order. The progress band is independent of the text renderer.
PAINT = [None, (96,160,16), (72,72,224), (224,160,72), (54,176,224)]

def exercise(hwnd, phase, current):
    host=terminal_host(hwnd); assert host!=hwnd
    u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
    assert int(u.GetPropW(hwnd,"NemotermRenderer") or 0)=={"gdi":1,"directx":3}[os.environ["RENDERER"]]
    pid=w.DWORD(); assert u.GetWindowThreadProcessId(host,c.byref(pid))
    surface=PresentedWindowCapture(pid.value,host)
    result=dict(cases=[],renderer=os.environ['RENDERER'],reference='TerminalApiTest::SetTaskbarProgress')
    tag='taskbar-progress-'+result['renderer']
    try:
        def frame():
            bmp=surface.capture();width,height=struct.unpack_from('<ii',bmp,18)
            return width,-height,bmp[54:]
        def tab_width():
            width,_,pixels=frame();row=pixels[width*4:2*width*4]
            if tuple(row[:3])!=(76,68,64):return None
            return next((x for x in range(1,width) if tuple(row[4*x:4*x+3])!=(76,68,64)),None)
        extent=wait_for(tab_width); result['tab_width']=extent
        for i,(name,payload,state,value) in enumerate(CASES):
            seq='\x1bc' if payload is None else '\x1b]9;'+payload+('\x07' if i%2 else '\x1b\\')
            phase(name,seq,''); until=time.monotonic()+1
            while True:
                width,height,pixels=frame()
                # Count each colour on its fullest scanline within the first tab.
                counts=[max(sum(pixels[(y*width+x)*4:(y*width+x)*4+3]==bytes(colour) for x in range(extent)) for y in range(min(48,height))) for colour in PAINT[1:]]
                target=[0]*4
                if state:target[state-1]=((extent//8)*4+min(extent%8,4)) if state==3 else extent*value//100
                if counts==target or time.monotonic()>=until:break
                time.sleep(.02)
            row=dict(name=name,sequence_hex=seq.encode().hex(),state=state,value=value,pixel_counts=counts,expected_counts=target,passed=counts==target)
            result['cases'].append(row)
            if not row['passed'] or name in ('normal','busy','paused-value'):
                crop=pixels[:width*min(48,height)*4];capture_result(width,min(48,height),crop,tag+'-'+name+'.png')
    finally:
        result['capture']=surface.close()
        (root/'research'/(tag+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    renderer=os.environ['RENDERER']; tag='taskbar-progress-'+renderer
    run(tag+'-window',[],exercise=exercise,font=os.environ['NEMOTERM_TEST_FONT'],
        profile=dict(NemoTabs=1,NemoTabSide=0,NemoRenderer={'gdi':0,'directx':2}[renderer]),
        source_reference='Pinned Microsoft Terminal TerminalApiTest::SetTaskbarProgress')
    report=json.loads((root/'research'/(tag+'.json')).read_bytes());assert len(report['cases'])==len(CASES)
    assert all(row['passed'] for row in report['cases']),[row for row in report['cases'] if not row['passed']]
