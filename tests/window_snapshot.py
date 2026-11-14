"""Bounded metadata for windows of a retained fixture-owned process.

Includes hidden, child and message-only HWNDs. No window text, messages, menu
creation/reset, injection or focus changes. USER counts include non-window
objects; counting HWNDs is not a complete USER-object census.
"""
import ctypes as c
from ctypes import wintypes as w
import time

u=c.WinDLL('user32',use_last_error=True)
callback=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
u.EnumWindows.argtypes=[callback,w.LPARAM]
u.EnumChildWindows.argtypes=[w.HWND,callback,w.LPARAM]
u.FindWindowExW.argtypes,u.FindWindowExW.restype=[w.HWND,w.HWND,w.LPCWSTR,w.LPCWSTR],w.HWND
u.GetWindowThreadProcessId.argtypes,u.GetWindowThreadProcessId.restype=[w.HWND,c.POINTER(w.DWORD)],w.DWORD
u.GetClassNameW.argtypes=[w.HWND,w.LPWSTR,c.c_int]
u.GetParent.argtypes,u.GetParent.restype=[w.HWND],w.HWND
u.GetWindow.argtypes,u.GetWindow.restype=[w.HWND,w.UINT],w.HWND
u.GetWindowLongPtrW.argtypes,u.GetWindowLongPtrW.restype=[w.HWND,c.c_int],c.c_ssize_t
u.IsWindowVisible.argtypes=[w.HWND]

class OwnedWindowSnapshot:
    def __init__(self,owner):
        self.owner=owner
        self.owner._validate_owner()

    def snapshot(self,label):
        self.owner._validate_owner();started=time.monotonic()
        pid=self.owner.process.pid;windows=[];seen=set();errors=[];visits=0
        @callback
        def visit(hwnd,descend):
            nonlocal visits
            try:
                visits+=1
                if visits>16384:raise RuntimeError('Window enumeration exceeds 16384 visits')
                if hwnd in seen:return True
                seen.add(hwnd)
                process=w.DWORD();tid=u.GetWindowThreadProcessId(hwnd,c.byref(process))
                if process.value!=pid:return True
                name=c.create_unicode_buffer(256)
                length=u.GetClassNameW(hwnd,name,len(name))
                if not length:
                    errors.append(dict(hwnd=hwnd,operation='class name',winerror=c.get_last_error()))
                    return True
                if length>=len(name)-1:raise RuntimeError('Class name may be truncated')
                entry=dict(hwnd=hwnd,tid=tid,kind=name.value,parent=u.GetParent(hwnd),
                    owner=u.GetWindow(hwnd,4),visible=bool(u.IsWindowVisible(hwnd)),
                    style=u.GetWindowLongPtrW(hwnd,-16)&0xffffffff,
                    extended_style=u.GetWindowLongPtrW(hwnd,-20)&0xffffffff)
                after=w.DWORD();after_tid=u.GetWindowThreadProcessId(hwnd,c.byref(after))
                if after.value!=pid or after_tid!=tid:
                    errors.append(dict(hwnd=hwnd,operation='identity changed during snapshot'))
                    return True
                windows.append(entry)
                if len(windows)>512:raise RuntimeError('Owned window inventory exceeds 512 HWNDs')
                if descend:u.EnumChildWindows(hwnd,visit,0)
                return not any('exception' in error for error in errors)
            except BaseException as error:
                errors.append(dict(exception=repr(error)))
                return False
        c.set_last_error(0)
        enumerated=u.EnumWindows(visit,1)
        if not enumerated and not any('exception' in error for error in errors):
            errors.append(dict(operation='EnumWindows',winerror=c.get_last_error()))
        message=None
        for _ in range(4096):
            message=u.FindWindowExW(w.HWND(-3),message,None,None)
            if not message:break
            if not visit(message,1):break
        else:errors.append(dict(exception='Message-only enumeration exceeds 4096 HWNDs'))
        self.owner._validate_owner()
        return dict(label=label,pid=pid,seconds=time.monotonic()-started,
                    windows=sorted(windows,key=lambda row:row['hwnd']),errors=errors,
                    caveat='Sequential samples; HWND reuse and non-window USER objects are not resolved.')
