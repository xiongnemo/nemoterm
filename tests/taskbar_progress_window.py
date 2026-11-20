"""Actual tab-strip pixels after a console child writes OSC 9;4. Hosted Windows only."""
import json
import os
import struct
import time
from native_test_utils import c, w, u, root, terminal_host, capture_result
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
        # The first tab is alone in a wide, non-overflow top strip. Derive its
        # published preferred width from host DPI, never from the colour of
        # its corners or from any progress pixels under test. Measure the
        # actual strip height from the terminal child in screen coordinates.
        u.GetDpiForWindow.argtypes=[w.HWND]; dpi=u.GetDpiForWindow(host); assert dpi>0
        origin=w.POINT(); child=w.RECT(); assert u.ClientToScreen(host,c.byref(origin))
        assert u.GetWindowRect(hwnd,c.byref(child)); strip_height=child.top-origin.y
        width,height,_=frame(); extent=(168*dpi+48)//96
        assert 0<strip_height<height and width>=extent+strip_height
        result.update(tab_width=extent,dpi=dpi,strip_height=strip_height,host_size=[width,height])
        colours={bytes(rgb):i for i,rgb in enumerate(PAINT[1:])}
        for i,(name,payload,state,value) in enumerate(CASES):
            seq='\x1bc' if payload is None else '\x1b]9;'+payload+('\x07' if i%2 else '\x1b\\')
            phase(name,seq,''); until=time.monotonic()+1
            while True:
                width,height,pixels=frame()
                assert [width,height]==result['host_size']
                # Compare exact painted positions across the whole strip.
                # This catches a shifted/over-wide fill, stray colour on
                # another row, or stripes with the correct count but phase.
                band=max(2,(3*dpi+48)//96); expected=set()
                if state:
                    columns=(x for x in range(extent) if x%8<4) if state==3 else range(extent*value//100)
                    expected={(x,y,state-1) for x in columns for y in range(strip_height-band,strip_height)}
                seen=set()
                for y in range(strip_height):
                    for x in range(width):
                        colour=colours.get(pixels[(y*width+x)*4:(y*width+x)*4+3])
                        if colour is not None:seen.add((x,y,colour))
                counts=[max((sum((x,y,c) in seen for x in range(extent)) for y in range(strip_height)),default=0) for c in range(4)]
                target=[0]*4
                if state:target[state-1]=len(expected)//band
                if seen==expected or time.monotonic()>=until:break
                time.sleep(.02)
            row=dict(name=name,sequence_hex=seq.encode().hex(),state=state,value=value,pixel_counts=counts,expected_counts=target,
                     missing_pixels=len(expected-seen),unexpected_pixels=len(seen-expected),passed=seen==expected)
            result['cases'].append(row)
            if not row['passed'] or name in ('normal','busy','paused-value'):
                crop=pixels[:width*strip_height*4];capture_result(width,strip_height,crop,tag+'-'+name+'.png')
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
