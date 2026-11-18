"""Observe only the fixture process's windows; acknowledge its own disconnect dialog."""
from native_test_utils import c, w, u, wait_for

Visit = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
u.GetWindow.argtypes, u.GetWindow.restype = [w.HWND, w.UINT], w.HWND
u.GetDlgCtrlID.argtypes = [w.HWND]
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


def acknowledge_disconnect(pid, hwnd, sibling, record):
    def dialog():
        matches = [row for row in owned_windows(pid) if row['owner'] == hwnd and
                   row['window_class'] == '#32770' and row['visible'] and row['enabled']]
        return matches[0]['hwnd'] if len(matches) == 1 else None
    dlg = wait_for(dialog)
    assert not u.IsWindowEnabled(hwnd) and not u.IsWindowEnabled(sibling)
    record.update(hwnd=dlg,states=[])
    def ready():
        controls=[]
        @Visit
        def visit(control, _):
            name=c.create_unicode_buffer(128);u.GetClassNameW(control,name,len(name))
            buf=c.create_unicode_buffer(160);result=c.c_size_t()
            # Standard cross-process WM_GETTEXT uses Windows marshalling.
            ok=u.SendMessageTimeoutW(control,0x0d,len(buf),c.addressof(buf),2,300,c.byref(result))
            controls.append(dict(hwnd=control,window_class=name.value,id=u.GetDlgCtrlID(control),
                                 text=buf.value if ok else None,enabled=bool(u.IsWindowEnabled(control)),
                                 visible=bool(u.IsWindowVisible(control))))
            return True
        u.EnumChildWindows(dlg,visit,0)
        if not record['states'] or record['states'][-1]!=controls:record['states'].append(controls)
        if not any(row['text']=='Connection closed by remote host' for row in controls):return None
        buttons=[row for row in controls if row['window_class']=='Button' and row['visible'] and row['enabled']]
        if len(buttons)!=1:return None
        button=buttons[0]
        return button['hwnd'] if button['id']==1 or (button['text'] or '').replace('&','').casefold()=='ok' else None
    ok=wait_for(ready)
    assert u.PostMessageW(ok, 0x00f5, 0, 0)  # BM_CLICK on the verified OK button
    wait_for(lambda: not u.IsWindow(dlg) and u.IsWindowEnabled(hwnd) and u.IsWindowEnabled(sibling))
    record.update(clicked=ok, both_owners_reenabled=True)
