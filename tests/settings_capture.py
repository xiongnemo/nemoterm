"""Capture only the owned settings dialog passed by settings_window_smoke.ps1."""
from native_test_utils import c,w,u,capture,sys

pid,hwnd=map(int,sys.argv[1:3])
u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
u.GetClassNameW.argtypes=[w.HWND,w.LPWSTR,c.c_int]
owner=w.DWORD(); name=c.create_unicode_buffer(64)
u.GetWindowThreadProcessId(hwnd,c.byref(owner)); u.GetClassNameW(hwnd,name,64)
assert owner.value==pid and name.value=='PuTTYConfigBox',(owner.value,name.value)
u.RedrawWindow.argtypes=[w.HWND,c.c_void_p,w.HANDLE,w.UINT]
assert u.RedrawWindow(hwnd,None,None,0x185)  # invalidate + all children + update now
capture(hwnd,sys.argv[3] if len(sys.argv)>3 else 'mok-settings.png')
