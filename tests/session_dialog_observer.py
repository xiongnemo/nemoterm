"""Observe only the fixture process's windows; acknowledge its own disconnect dialog."""
from native_test_utils import c, w, u, wait_for

Visit = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
u.GetWindow.argtypes, u.GetWindow.restype = [w.HWND, w.UINT], w.HWND
u.GetDlgItem.argtypes, u.GetDlgItem.restype = [w.HWND, c.c_int], w.HWND
u.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
u.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, c.c_int]
u.SendMessageTimeoutW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM, w.UINT, w.UINT, c.POINTER(c.c_size_t)]
u.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]


def owned_windows(pid):
    items = []
    @Visit
    def visit(hwnd, _):
        owner = w.DWORD(); tid = u.GetWindowThreadProcessId(hwnd, c.byref(owner))
        if owner.value == pid:
            name = c.create_unicode_buffer(128)
            u.GetClassNameW(hwnd, name, len(name))
            items.append(dict(hwnd=hwnd, thread=tid, window_class=name.value,
                              owner=u.GetWindow(hwnd, 4), visible=bool(u.IsWindowVisible(hwnd)),
                              enabled=bool(u.IsWindowEnabled(hwnd))))
        return True
    assert u.EnumWindows(visit, 0)
    return items


def acknowledge_disconnect(pid, hwnd, sibling):
    def dialog():
        matches = [row for row in owned_windows(pid) if row['owner'] == hwnd and
                   row['window_class'] == '#32770' and row['visible'] and row['enabled']]
        return matches[0]['hwnd'] if len(matches) == 1 else None
    dlg = wait_for(dialog)
    assert not u.IsWindowEnabled(hwnd) and not u.IsWindowEnabled(sibling)
    texts = []
    @Visit
    def visit(control, _):
        buf = c.create_unicode_buffer(160); result = c.c_size_t()
        # WM_GETTEXT is marshalled by the OS for standard cross-process controls.
        if u.SendMessageTimeoutW(control, 0x0d, len(buf), c.addressof(buf), 2, 300, c.byref(result)):
            texts.append(buf.value)
        return True
    u.EnumChildWindows(dlg, visit, 0)
    assert 'Connection closed by remote host' in texts, texts
    ok = u.GetDlgItem(dlg, 1); assert ok and u.IsWindowEnabled(ok)
    assert u.PostMessageW(ok, 0x00f5, 0, 0)  # BM_CLICK on the verified OK button
    wait_for(lambda: not u.IsWindow(dlg) and u.IsWindowEnabled(hwnd) and u.IsWindowEnabled(sibling))
    return dict(hwnd=dlg, text='Connection closed by remote host', both_owners_reenabled=True)
