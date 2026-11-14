"""Read an owned visible GDI client DC without requesting WM_PRINTCLIENT.

This interactive-desktop probe raises only its fixture-owned HWND without
activation. It does not read the desktop DC, move the pointer, or send keys.
https://learn.microsoft.com/windows/win32/gdi/capturing-an-image
"""
import struct
from native_test_utils import c,w,u,g

u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
u.GetClientRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
u.GetWindowLongW.argtypes,u.GetWindowLongW.restype=[w.HWND,c.c_int],w.LONG
u.SetWindowPos.argtypes=[w.HWND,w.HWND,c.c_int,c.c_int,c.c_int,c.c_int,w.UINT]
u.IsWindowVisible.argtypes=u.IsIconic.argtypes=[w.HWND]
g.BitBlt.argtypes=[w.HDC,c.c_int,c.c_int,c.c_int,c.c_int,w.HDC,c.c_int,c.c_int,w.DWORD]


class PresentedWindowCapture:
    def __init__(self,pid,hwnd):
        self.pid=pid;self.hwnd=hwnd;self.closed=False
        self.record=dict(method='GetDC(owned HWND) + BitBlt',pid=pid,hwnd=hwnd,
            desktop_dc=False,wm_print=False,activation=False,captures=0)
        self._owner()
        assert u.IsWindowVisible(hwnd) and not u.IsIconic(hwnd)
        self.was_topmost=bool(u.GetWindowLongW(hwnd,-20)&8)
        assert u.SetWindowPos(hwnd,-1,0,0,0,0,0x13) # topmost, no move/size/activation
        self.record['temporarily_topmost']=not self.was_topmost

    def _owner(self):
        owner=w.DWORD()
        assert u.GetWindowThreadProcessId(self.hwnd,c.byref(owner)) and owner.value==self.pid

    def capture(self):
        assert not self.closed
        self._owner()
        rect=w.RECT();assert u.GetClientRect(self.hwnd,c.byref(rect))
        width,height=rect.right,rect.bottom;size=width*height*4
        assert width>0 and height>0 and size<=8*1024*1024
        header=struct.pack('<IiiHHIIiiII',40,width,-height,1,32,0,size,0,0,0,0)
        info=c.create_string_buffer(header);bits=c.c_void_p()
        src=u.GetDC(self.hwnd);assert src
        dst=bitmap=old=None
        try:
            dst=g.CreateCompatibleDC(src);assert dst
            bitmap=g.CreateDIBSection(src,info,0,c.byref(bits),None,0);assert bitmap and bits.value
            old=g.SelectObject(dst,bitmap);assert old and old!=c.c_void_p(-1).value
            c.memset(bits,0,size)
            assert g.BitBlt(dst,0,0,width,height,src,0,0,0x00cc0020)
            g.GdiFlush()
            pixels=c.string_at(bits,size)
            self.record['captures']+=1
            return struct.pack('<2sIHHI',b'BM',54+size,0,0,54)+header+pixels
        finally:
            if old and old!=c.c_void_p(-1).value:g.SelectObject(dst,old)
            if bitmap:g.DeleteObject(bitmap)
            if dst:g.DeleteDC(dst)
            u.ReleaseDC(self.hwnd,src)

    def close(self):
        if self.closed:return self.record
        owner=w.DWORD()
        same=u.GetWindowThreadProcessId(self.hwnd,c.byref(owner)) and owner.value==self.pid
        if same and not self.was_topmost:
            assert u.SetWindowPos(self.hwnd,-2,0,0,0,0,0x13)
            self.record['topmost_restored']=True
        self.record['closed']=True
        self.closed=True
        return self.record
