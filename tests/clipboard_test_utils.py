"""Preserve HGLOBAL clipboard formats around tests of an owned HWND.

Refuse unsupported handle formats before modifying anything. If another
application changes the clipboard during the test, leave its new content alone.
"""
from native_test_utils import c, w, u, k, wait_for

u.OpenClipboard.argtypes = [w.HWND]
u.GetClipboardOwner.restype = w.HWND
u.GetClipboardData.argtypes, u.GetClipboardData.restype = [w.UINT], w.HANDLE
u.SetClipboardData.argtypes, u.SetClipboardData.restype = [w.UINT, w.HANDLE], w.HANDLE
k.GlobalSize.argtypes, k.GlobalSize.restype = [w.HANDLE], c.c_size_t
k.GlobalLock.argtypes, k.GlobalLock.restype = [w.HANDLE], c.c_void_p
k.GlobalUnlock.argtypes = [w.HANDLE]
k.GlobalAlloc.argtypes, k.GlobalAlloc.restype = [w.UINT, c.c_size_t], w.HANDLE
k.GlobalFree.argtypes = [w.HANDLE]

class SavedClipboard:
    def __init__(self, hwnd):
        self.hwnd, self.saved = hwnd, []
        wait_for(lambda: u.OpenClipboard(hwnd))
        try:
            fmt = 0
            while (fmt := u.EnumClipboardFormats(fmt)):
                handle = u.GetClipboardData(fmt)
                size = k.GlobalSize(handle)
                assert size, f'Cannot preserve clipboard format {fmt}; nothing was modified'
                ptr = k.GlobalLock(handle)
                assert ptr, f'Cannot lock clipboard format {fmt}; nothing was modified'
                try:
                    self.saved.append((fmt, c.string_at(ptr, size)))
                finally:
                    k.GlobalUnlock(handle)
        finally:
            u.CloseClipboard()

    def restore(self):
        if u.GetClipboardOwner() != self.hwnd:
            return
        wait_for(lambda: u.OpenClipboard(self.hwnd))
        pending = []
        try:
            if u.GetClipboardOwner() != self.hwnd:
                return
            for fmt, data in self.saved:
                handle = k.GlobalAlloc(2, len(data))
                assert handle
                pending.append((fmt, handle))
                ptr = k.GlobalLock(handle)
                assert ptr
                c.memmove(ptr, data, len(data)); k.GlobalUnlock(handle)
            assert u.EmptyClipboard()
            while pending:
                fmt, handle = pending[0]
                if not u.SetClipboardData(fmt, handle):
                    raise c.WinError()
                pending.pop(0)  # clipboard now owns the handle
        finally:
            for _, handle in pending:
                k.GlobalFree(handle)
            u.CloseClipboard()

def clipboard_text(hwnd):
    wait_for(lambda: u.OpenClipboard(hwnd))
    try:
        handle = u.GetClipboardData(13)  # CF_UNICODETEXT
        if not handle:
            return None
        ptr = k.GlobalLock(handle)
        assert ptr
        try:
            return c.wstring_at(ptr)
        finally:
            k.GlobalUnlock(handle)
    finally:
        u.CloseClipboard()
