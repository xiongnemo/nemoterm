"""Owned ConPTY client: ordered VT barriers and explicit window operations."""
import ctypes as c
from ctypes import wintypes as w
import os
from pathlib import Path
import sys,threading,time
from fixture_io import read_snapshot,write_snapshot

directory=Path(sys.argv[1]);k=c.WinDLL('kernel32',use_last_error=True);u=c.windll.user32
k.GetStdHandle.argtypes,k.GetStdHandle.restype=[w.DWORD],w.HANDLE
k.GetConsoleWindow.restype=w.HWND
k.SetConsoleMode.argtypes=[w.HANDLE,w.DWORD]
k.ReadFile.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p]
u.ShowWindow.argtypes=[w.HWND,c.c_int]
stdin=k.GetStdHandle(-10);assert k.SetConsoleMode(stdin,0x280)
received=bytearray();lock=threading.Lock()
def reader():
    buffer=c.create_string_buffer(1024);count=w.DWORD()
    while k.ReadFile(stdin,buffer,len(buffer),c.byref(count),None) and count.value:
        with lock:received.extend(buffer.raw[:count.value])
threading.Thread(target=reader,daemon=True).start()
sys.stdout.reconfigure(encoding='utf-8',newline='')
phase=-1;deadline=time.monotonic()+60
while time.monotonic()<deadline:
    request=read_snapshot(directory/'control.json') or dict(phase=0,operation='ready')
    if request.get('stop'):break
    if request['phase']!=phase:
        phase=request['phase'];operation=request['operation']
        with lock:received.clear()
        if operation=='vt_minimize':print('\x1b[2t',end='',flush=True)
        elif operation=='vt_restore':print('\x1b[1t',end='',flush=True)
        elif operation in ('native_minimize','native_restore'):
            hwnd=k.GetConsoleWindow();assert hwnd
            u.ShowWindow(hwnd,6 if operation=='native_minimize' else 4)
        else:assert operation=='ready'
        print('\x1b[5n',end='',flush=True)
        end=time.monotonic()+5
        while time.monotonic()<end:
            with lock:done=b'\x1b[0n' in received
            if done:break
            time.sleep(.01)
        assert done,'DSR barrier was not acknowledged'
        size=os.get_terminal_size()
        write_snapshot(directory/'report.json',dict(phase=phase,operation=operation,
            pid=os.getpid(),columns=size.columns,rows=size.lines,barrier=done))
    time.sleep(.01)
