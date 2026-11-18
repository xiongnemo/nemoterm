"""Read only the visible character cells of a disposable test process's own console."""
import ctypes as c
from ctypes import wintypes as w
import os
from pathlib import Path
import subprocess
import sys
import time
from fixture_io import write_snapshot

k=c.windll.kernel32
class Coord(c.Structure):
    _fields_=[('x',c.c_short),('y',c.c_short)]


class Rect(c.Structure):
    _fields_=[('left',c.c_short),('top',c.c_short),('right',c.c_short),('bottom',c.c_short)]


class Info(c.Structure):
    _fields_=[('size',Coord),('cursor',Coord),('attrs',w.WORD),('view',Rect),('maximum',Coord)]


def console_view(handle):
    # WinPTY emits damage, not complete frames. Read only this wrapper's own
    # visible console rectangle; never capture the Windows desktop.
    info=Info()
    if not k.GetConsoleScreenBufferInfo(handle,c.byref(info)):return None
    r=info.view;width=r.right-r.left+1
    if not 0<width<=200 or not 0<r.bottom-r.top+1<=80:return None
    buf=c.create_unicode_buffer(width+1);rows=[];count=w.DWORD()
    for y in range(r.top,r.bottom+1):
        if not k.ReadConsoleOutputCharacterW(handle,buf,width,Coord(r.left,y),c.byref(count)) or count.value!=width:return None
        rows.append(buf[:width].rstrip())
    return '\n'.join(rows)


class ConsoleView:
    def __init__(self,folder):
        if os.environ.get('NEMOTERM_HOSTED_REFERENCE')!='1':raise RuntimeError('Hosted reference child required')
        k.GetStdHandle.argtypes=[w.DWORD];k.GetStdHandle.restype=w.HANDLE
        k.GetConsoleScreenBufferInfo.argtypes=[w.HANDLE,c.POINTER(Info)]
        k.ReadConsoleOutputCharacterW.argtypes=[w.HANDLE,w.LPWSTR,w.DWORD,Coord,c.POINTER(w.DWORD)]
        self.folder=folder;self.handle=k.GetStdHandle(-11);self.previous=None

    def capture(self):
        frame=console_view(self.handle)
        if frame is not None and frame!=self.previous:
            write_snapshot(self.folder/'peer-screen.json',dict(text=frame));self.previous=frame


def observe(folder,command):
    view=ConsoleView(folder);child=subprocess.Popen(command)
    while child.poll() is None:
        view.capture();time.sleep(.025)
    return child.returncode


if __name__=='__main__':sys.exit(observe(Path(sys.argv[1]),sys.argv[2:]))
