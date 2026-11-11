"""Hidden clipboard owner for testing delayed rendering, controlled by JSON."""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
import sys
import time
from fixture_io import read_snapshot,write_snapshot

report,control=map(Path,sys.argv[1:3])
u,k=c.windll.user32,c.windll.kernel32
LRESULT=c.c_ssize_t
WNDPROC=c.WINFUNCTYPE(LRESULT,w.HWND,w.UINT,w.WPARAM,w.LPARAM)
class WNDCLASS(c.Structure):
    _fields_=[('style',w.UINT),('proc',WNDPROC),('cls_extra',c.c_int),('wnd_extra',c.c_int),
              ('instance',w.HINSTANCE),('icon',w.HICON),('cursor',w.HANDLE),('background',w.HBRUSH),
              ('menu',w.LPCWSTR),('name',w.LPCWSTR)]
u.DefWindowProcW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]; u.DefWindowProcW.restype=LRESULT
u.RegisterClassW.argtypes=[c.POINTER(WNDCLASS)]
u.CreateWindowExW.argtypes=[w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,c.c_int,c.c_int,c.c_int,c.c_int,
                           w.HWND,w.HMENU,w.HINSTANCE,c.c_void_p]
u.CreateWindowExW.restype=w.HWND
u.OpenClipboard.argtypes=[w.HWND]
u.GetClipboardOwner.restype=w.HWND
u.SetClipboardData.argtypes=[w.UINT,w.HANDLE]; u.SetClipboardData.restype=w.HANDLE
u.DestroyWindow.argtypes=[w.HWND]
u.PeekMessageW.argtypes=[c.POINTER(w.MSG),w.HWND,w.UINT,w.UINT,w.UINT]
u.DispatchMessageW.argtypes=[c.POINTER(w.MSG)]; u.DispatchMessageW.restype=LRESULT
k.GetModuleHandleW.argtypes=[w.LPCWSTR]; k.GetModuleHandleW.restype=w.HMODULE
k.GlobalAlloc.argtypes=[w.UINT,c.c_size_t]; k.GlobalAlloc.restype=w.HGLOBAL
k.GlobalLock.argtypes=[w.HGLOBAL]; k.GlobalLock.restype=c.c_void_p
k.GlobalUnlock.argtypes=[w.HGLOBAL]

def render():
    data=('delayed clipboard 秘密 😀\0').encode('utf-16-le')
    memory=k.GlobalAlloc(2,len(data)); assert memory
    pointer=k.GlobalLock(memory); assert pointer
    c.memmove(pointer,data,len(data)); k.GlobalUnlock(memory)
    assert u.SetClipboardData(13,memory)

@WNDPROC
def wndproc(hwnd,message,wp,lp):
    if message==0x305 and wp==13:  # WM_RENDERFORMAT, caller already holds clipboard
        write_snapshot(report,{'state':'rendering','hwnd':int(hwnd)})
        deadline=time.monotonic()+5
        while not read_snapshot(control).get('release') and time.monotonic()<deadline:
            time.sleep(.01)
        render()
        write_snapshot(report,{'state':'rendered','hwnd':int(hwnd)})
        return 0
    if message==0x306:  # WM_RENDERALLFORMATS before destruction
        if u.OpenClipboard(hwnd):
            try:
                if u.GetClipboardOwner()==hwnd: render()
            finally: u.CloseClipboard()
        return 0
    return u.DefWindowProcW(hwnd,message,wp,lp)

instance=k.GetModuleHandleW(None)
cls=WNDCLASS(proc=wndproc,instance=instance,name='NemoOSC52DelayedFixture')
assert u.RegisterClassW(c.byref(cls))
hwnd=u.CreateWindowExW(0,cls.name,'OSC 52 fixture',0,0,0,1,1,None,None,instance,None)
assert hwnd
deadline=time.monotonic()+3
while not u.OpenClipboard(hwnd):
    if time.monotonic()>deadline: raise c.WinError()
    time.sleep(.01)
try:
    assert u.EmptyClipboard()
    u.SetClipboardData(13,None)  # Successful delayed publication also returns NULL.
finally:
    u.CloseClipboard()
write_snapshot(report,{'state':'ready','hwnd':int(hwnd)})
deadline=time.monotonic()+20
message=w.MSG()
while not read_snapshot(control).get('stop') and time.monotonic()<deadline:
    while u.PeekMessageW(c.byref(message),None,0,0,1):
        u.DispatchMessageW(c.byref(message))
    time.sleep(.005)
u.DestroyWindow(hwnd)
