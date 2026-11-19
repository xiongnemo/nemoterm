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


class Cell(c.Structure):  # CHAR_INFO's UTF-16 union and console attributes
    _fields_=[('unit',w.WORD),('attributes',w.WORD)]


def cell_view(handle):
    info=Info()
    if not k.GetConsoleScreenBufferInfo(handle,c.byref(info)):return None
    r=info.view; coords=(r.left,r.top,r.right,r.bottom)
    width=r.right-r.left+1; height=r.bottom-r.top+1
    if not (0<width<=200 and 0<height<=80):return None
    cells=(Cell*(width*height))()
    if not k.ReadConsoleOutputW(handle,cells,Coord(width,height),Coord(0,0),c.byref(r)):return None
    if (r.left,r.top,r.right,r.bottom)!=coords:return None  # clipped read
    rows=[]
    for y in range(height):
        row=cells[y*width:(y+1)*width]
        rows.append(''.join(chr(v.unit) for v in row if not v.attributes & 0x0200).rstrip())
    return '\n'.join(rows)


class ConsoleView:
    def __init__(self,folder,compare_cells=False):
        if os.environ.get('NEMOTERM_HOSTED_REFERENCE')!='1':raise RuntimeError('Hosted reference child required')
        k.GetStdHandle.argtypes=[w.DWORD];k.GetStdHandle.restype=w.HANDLE
        k.GetConsoleScreenBufferInfo.argtypes=[w.HANDLE,c.POINTER(Info)]
        k.ReadConsoleOutputCharacterW.argtypes=[w.HANDLE,w.LPWSTR,w.DWORD,Coord,c.POINTER(w.DWORD)]
        self.compare_cells=compare_cells
        if compare_cells:
            k.ReadConsoleOutputW.argtypes=[w.HANDLE,c.POINTER(Cell),Coord,Coord,c.POINTER(Rect)]
            k.ReadConsoleOutputW.restype=w.BOOL
        self.folder=folder;self.handle=k.GetStdHandle(-11);self.previous=None

    def capture(self):
        legacy=console_view(self.handle)
        frame=cell_view(self.handle) if self.compare_cells else legacy
        if frame is not None and frame!=self.previous:
            record=dict(text=frame)
            if self.compare_cells:
                record.update(reader='ReadConsoleOutputW',legacy_available=legacy is not None,
                              legacy_ack_lines=[] if legacy is None else [s for s in legacy.splitlines() if 'ACKTURN' in s],
                              wide_probe_seen=legacy is not None and 'CELL中Z' in legacy)
            write_snapshot(self.folder/'peer-screen.json',record);self.previous=frame


def observe(folder,command):
    view=ConsoleView(folder)
    # GetStdHandle identifies the inherited buffer. A client can activate
    # another buffer; opening CONOUT$ reads the one active at that instant.
    k.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,w.DWORD,w.HANDLE]
    k.CreateFileW.restype=w.HANDLE;k.CloseHandle.argtypes=[w.HANDLE]
    invalid=c.c_void_p(-1).value; token='NEMOTERM_TEXT_ACCEPTED';prev=None
    record=dict(captures=0,unavailable=0,first_token_ns=None)
    child=subprocess.Popen(command)
    try:
        while child.poll() is None:
            view.capture();handle=k.CreateFileW('CONOUT$',0x80000000,3,None,3,0,None)
            if handle not in (None,invalid):
                try:active=console_view(handle)
                finally:k.CloseHandle(handle)
            else:active=None
            if active is None:record['unavailable']+=1
            else:
                record['captures']+=1
                if active!=prev:
                    stamp=time.monotonic_ns();prev=active
                    write_snapshot(folder/'peer-active-screen.json',dict(text=active,monotonic_ns=stamp))
                    if record['first_token_ns'] is None and token in active:
                        record['first_token_ns']=stamp
                        write_snapshot(folder/'peer-active-first-reply.json',dict(text=active,monotonic_ns=stamp))
            time.sleep(.025)
    finally:write_snapshot(folder/'peer-active-stats.json',record)
    return child.returncode

if __name__=='__main__':sys.exit(observe(Path(sys.argv[1]),sys.argv[2:]))
