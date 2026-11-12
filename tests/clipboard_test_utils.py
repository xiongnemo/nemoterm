"""Preserve HGLOBAL, bitmap and palette clipboard formats for an owned HWND.

Refuse unsupported handle formats before modifying anything. If another
application changes the clipboard during the test, leave its new content alone.
"""
from native_test_utils import c, w, u, g, k, wait_for

u.OpenClipboard.argtypes = [w.HWND]
u.GetClipboardOwner.restype = w.HWND
u.GetClipboardData.argtypes, u.GetClipboardData.restype = [w.UINT], w.HANDLE
u.SetClipboardData.argtypes, u.SetClipboardData.restype = [w.UINT, w.HANDLE], w.HANDLE
k.GlobalSize.argtypes, k.GlobalSize.restype = [w.HANDLE], c.c_size_t
k.GlobalLock.argtypes, k.GlobalLock.restype = [w.HANDLE], c.c_void_p
k.GlobalUnlock.argtypes = [w.HANDLE]
k.GlobalAlloc.argtypes, k.GlobalAlloc.restype = [w.UINT, c.c_size_t], w.HANDLE
k.GlobalFree.argtypes = [w.HANDLE]
ole = c.windll.ole32
ole.OleDuplicateData.argtypes = [w.HANDLE, w.WORD, w.UINT]
ole.OleDuplicateData.restype = w.HANDLE
# https://learn.microsoft.com/windows/win32/api/ole2/nf-ole2-oleduplicatedata
# These clipboard entries are GDI objects, not GlobalAlloc blocks.
GDI_FORMATS = (2, 9, 0x82)  # CF_BITMAP, CF_PALETTE, CF_DSPBITMAP

def duplicate_gdi(fmt, handle):
    return ole.OleDuplicateData(handle, 2 if fmt == 0x82 else fmt, 0)

def free_saved_handle(fmt, handle):
    if fmt in GDI_FORMATS:
        g.DeleteObject(handle)
    else:
        k.GlobalFree(handle)

class SavedClipboard:
    def __init__(self, hwnd):
        self.hwnd, self.saved = hwnd, []
        wait_for(lambda: u.OpenClipboard(hwnd))
        try:
            fmt = 0
            while (fmt := u.EnumClipboardFormats(fmt)):
                handle = u.GetClipboardData(fmt)
                if fmt in GDI_FORMATS:
                    copied = duplicate_gdi(fmt, handle)
                    assert copied, f'Cannot preserve GDI clipboard format {fmt}; nothing was modified'
                    self.saved.append((fmt, copied))
                    continue
                size = k.GlobalSize(handle)
                assert size, f'Cannot preserve clipboard format {fmt}; nothing was modified'
                ptr = k.GlobalLock(handle)
                assert ptr, f'Cannot lock clipboard format {fmt}; nothing was modified'
                try:
                    self.saved.append((fmt, c.string_at(ptr, size)))
                finally:
                    k.GlobalUnlock(handle)
        except BaseException:
            self.dispose()
            raise
        finally:
            u.CloseClipboard()

    def dispose(self):
        for fmt, data in self.saved:
            if fmt in GDI_FORMATS:
                g.DeleteObject(data)
        self.saved = []

    def restore(self):
        if u.GetClipboardOwner() != self.hwnd:
            self.dispose()
            return
        wait_for(lambda: u.OpenClipboard(self.hwnd))
        pending = []
        try:
            if u.GetClipboardOwner() != self.hwnd:
                return
            for fmt, data in self.saved:
                if fmt in GDI_FORMATS:
                    handle = duplicate_gdi(fmt, data)
                    assert handle
                    pending.append((fmt, handle))
                    continue
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
            for fmt, handle in pending:
                free_saved_handle(fmt, handle)
            self.dispose()
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
