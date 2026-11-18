"""Measure XTWINOPS 10 at the actual top-level HWND on the hosted desktop."""
import ctypes as c
from ctypes import wintypes as w
import time
from fixture_io import read_snapshot, wait_snapshot, write_snapshot
from native_test_utils import u


def check(host, monitor_rect, control, report, mode, permitted):
    caption, frame = 0x00c00000, 0x00040000
    u.GetWindowLongW.argtypes = [w.HWND, c.c_int]
    u.GetWindowLongW.restype = w.LONG
    def rect(r): return [r.left, r.top, r.right, r.bottom]
    def state():
        r = w.RECT(); assert u.GetWindowRect(host, c.byref(r))
        return dict(rect=rect(r), furniture=u.GetWindowLongW(host,-16)&(caption|frame), zoomed=bool(u.IsZoomed(host)))
    initial=state(); assert initial['furniture']&caption
    evidence=mode['fullscreen']=dict(initial=initial, monitor=rect(monitor_rect), steps=[])
    def step(name, operations, full, normal=initial):
        row=dict(name=name, operations=operations, expected_full=full); evidence['steps'].append(row)
        phase='fullscreen-'+name
        write_snapshot(control,dict(phase=phase, sequence=''.join('\x1b['+op+'t' for op in operations)+'\x1b[5n'))
        wait_snapshot(lambda:read_snapshot(report), lambda r:r.get('phase')==phase and r.get('hex')=='1b5b306e')
        # Application processing, WM_SIZE and the child console use different
        # queues. Require the observed Win32 state to survive multiple updates.
        end=time.monotonic()+3; stable=None
        while time.monotonic()<end:
            v=row['observed']=state(); now=time.monotonic()
            match=(v['rect']==rect(monitor_rect) and v['furniture']==0) if full else v==normal
            if match:
                if stable is None:stable=now
                if now-stable>=.12: return
            else:stable=None
            time.sleep(.02)
        raise AssertionError(row)
    if not permitted:
        step('denied-enter',['10;1'],False);step('denied-toggle',['10;2'],False);return
    step('enter',['10;1'],True);step('enter-again',['10;1'],True)
    step('leave',['10;0'],False);step('leave-again',['10;0'],False)
    step('toggle-in',['10;2'],True);step('toggle-out',['10;2'],False)
    step('twice-in-one-write',['10;2','10;2'],False)
    step('enter-and-two-toggles',['10;1','10;2','10;2'],True);step('default-restores',['10'],False)
    step('extra-argument',['10;1;7'],True);step('unknown-restores',['10;9'],False)
    step('subparameter-ignored',['10;1:7'],False)
    # Maximising keeps the caption and uses the work area. Fullscreen must
    # restore that distinct initial state, not switch to a normal-size window.
    u.ShowWindow(host,3)
    try:
        assert u.IsZoomed(host); maximized=state(); assert maximized['furniture']&caption
        step('from-maximized',['10;1'],True);step('back-to-maximized',['10;0'],False,normal=maximized)
    finally:u.ShowWindow(host,9)
