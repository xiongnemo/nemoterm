"""Prepare real focus on a fixture-owned window with explicit desktop opt-in.

SetForegroundWindow can be refused after another fixture received input. A
checked caption click establishes focus without changing foreground-lock policy
or faking WM_SETFOCUS. This helper is never used during a bell observation.
"""
import os
from native_test_utils import c, w, u, time, wait_for, terminal_host

class MouseInput(c.Structure):
    _fields_ = [('x', w.LONG), ('y', w.LONG), ('data', w.DWORD),
                ('flags', w.DWORD), ('time', w.DWORD), ('extra', c.c_size_t)]

class Input(c.Structure):
    # MOUSEINPUT is the largest member of the native INPUT union.
    _fields_ = [('kind', w.DWORD), ('mouse', MouseInput)]

u.GetForegroundWindow.restype = w.HWND
u.SetForegroundWindow.argtypes = [w.HWND]
u.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
u.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.GetWindowLongPtrW.argtypes, u.GetWindowLongPtrW.restype = [w.HWND, c.c_int], c.c_ssize_t
u.SetWindowPos.argtypes = [w.HWND, w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT]
u.WindowFromPoint.argtypes, u.WindowFromPoint.restype = [w.POINT], w.HWND
u.SetCursorPos.argtypes = [c.c_int, c.c_int]
u.GetCursorPos.argtypes = [c.POINTER(w.POINT)]
u.SendMessageW.restype = c.c_ssize_t
u.SendInput.argtypes = [w.UINT, c.POINTER(Input), c.c_int]

def focus_owned_window(window, owner_pid, *, allow_local=False):
    assert os.environ.get('GITHUB_ACTIONS') == 'true' or allow_local, 'Local foreground preparation requires explicit opt-in'
    owner = w.DWORD()
    assert u.IsWindow(window) and terminal_host(window) == window
    assert u.GetWindowThreadProcessId(window, c.byref(owner)) and owner.value == owner_pid
    record = dict(window=window, owner_pid=owner_pid, before=u.GetForegroundWindow())
    if record['before'] == window:
        record['method'] = 'already-foreground'
    else:
        record['set_foreground_result'] = bool(u.SetForegroundWindow(window))
        record['method'] = 'SetForegroundWindow'
        if u.GetForegroundWindow() != window:
            # Expose only this owned caption, preserving its topmost attribute.
            topmost = bool(u.GetWindowLongPtrW(window, -20) & 8)
            original = w.POINT();assert u.GetCursorPos(c.byref(original))
            point = None
            try:
                assert u.SetWindowPos(window, -1, 0, 0, 0, 0, 0x13)
                bounds = w.RECT()
                assert u.GetWindowRect(window, c.byref(bounds))
                record['bounds']=[bounds.left,bounds.top,bounds.right,bounds.bottom]
                record['style']=int(u.GetWindowLongPtrW(window,-16))
                record['caption_candidates']=[]
                x = (bounds.left + bounds.right) // 2
                for y in range(bounds.top + 6, min(bounds.top + 60, bounds.bottom), 2):
                    candidate = w.POINT(x, y)
                    packed = (x & 0xffff) | ((y & 0xffff) << 16)
                    under=u.WindowFromPoint(candidate)
                    hit=int(u.SendMessageW(window,0x84,0,packed))
                    record['caption_candidates'].append(dict(x=x,y=y,window=under,hit=hit))
                    if under == window and hit == 2:
                        point = candidate
                        break
                assert point is not None, ('No exposed owned caption', record)
                assert u.SetCursorPos(point.x, point.y)
                assert u.WindowFromPoint(point) == window
                clicks = (Input * 2)()
                clicks[0].mouse.flags, clicks[1].mouse.flags = 2, 4
                sent = u.SendInput(2, clicks, c.sizeof(Input))
                if sent == 1:
                    u.SendInput(1, c.byref(clicks[1]), c.sizeof(Input))
                assert sent == 2, ('Caption click failed', sent, record)
                record.update(method='owned-caption-click', click=[point.x, point.y])
            finally:
                if not topmost:u.SetWindowPos(window, -2, 0, 0, 0, 0, 0x13)
                current = w.POINT()
                if point is not None and u.GetCursorPos(c.byref(current)) and (current.x,current.y)==(point.x,point.y):
                    record['cursor_restored']=bool(u.SetCursorPos(original.x,original.y))
            assert bool(u.GetWindowLongPtrW(window, -20) & 8) == topmost
    wait_for(lambda: u.GetForegroundWindow() == window)
    time.sleep(.06)
    record['after'] = u.GetForegroundWindow()
    assert record['after'] == window, record
    return record
