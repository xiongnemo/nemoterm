"""Read real console INPUT_RECORDs or UTF-8 VT input from a ConPTY child."""
import ctypes as c
from ctypes import wintypes as w
import os
from pathlib import Path
import sys
import threading
import time
import traceback
from fixture_io import read_snapshot, write_snapshot

report,control=map(Path,sys.argv[1:3])
vt='--vt' in sys.argv[3:]
read_batch=int(sys.argv[sys.argv.index('--batch')+1]) if '--batch' in sys.argv[3:] else 128
assert 1 <= read_batch <= 128
k=c.windll.kernel32
k.GetStdHandle.argtypes=[w.DWORD];k.GetStdHandle.restype=w.HANDLE
k.GetConsoleMode.argtypes=[w.HANDLE,c.POINTER(w.DWORD)]
k.SetConsoleMode.argtypes=[w.HANDLE,w.DWORD]
k.FlushConsoleInputBuffer.argtypes=[w.HANDLE]
k.ReadFile.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p]
class Coord(c.Structure):
    _fields_=[('x',c.c_short),('y',c.c_short)]
class Key(c.Structure):
    _fields_=[('down',w.BOOL),('repeat',w.WORD),('vk',w.WORD),('scan',w.WORD),
              ('character',w.WORD),('control',w.DWORD)]
class Mouse(c.Structure):
    _fields_=[('position',Coord),('buttons',w.DWORD),('control',w.DWORD),('flags',w.DWORD)]
class Event(c.Union):
    _fields_=[('key',Key),('mouse',Mouse),('size',Coord),('focus',w.BOOL)]
class Record(c.Structure):
    _fields_=[('type',w.WORD),('event',Event)]
k.ReadConsoleInputW.argtypes=[w.HANDLE,c.POINTER(Record),w.DWORD,c.POINTER(w.DWORD)]
stdin=k.GetStdHandle(-10)
old=w.DWORD()
assert k.GetConsoleMode(stdin,c.byref(old))
input_mode=0x280 if vt else 0x98
assert k.SetConsoleMode(stdin,input_mode)
events=[];data=bytearray();signals=[];lock=threading.Lock()
@c.WINFUNCTYPE(w.BOOL,w.DWORD)
def control_handler(kind):
    with lock: signals.append(kind)
    return True
k.SetConsoleCtrlHandler.argtypes=[c.c_void_p,w.BOOL]
assert k.SetConsoleCtrlHandler(control_handler,True)
def reader():
    count=w.DWORD()
    if vt:
        buf=c.create_string_buffer(4096)
        while k.ReadFile(stdin,buf,len(buf),c.byref(count),None) and count.value:
            with lock: data.extend(buf.raw[:count.value])
    else:
        buf=(Record*read_batch)()
        while k.ReadConsoleInputW(stdin,buf,len(buf),c.byref(count)):
            batch=[]
            for record in buf[:count.value]:
                event=record.event
                if record.type==1:
                    batch.append(dict(type='key',**{name:getattr(event.key,name) for name,_ in Key._fields_}))
                elif record.type==2:
                    batch.append(dict(type='mouse',x=event.mouse.position.x,y=event.mouse.position.y,
                                      buttons=event.mouse.buttons,control=event.mouse.control,flags=event.mouse.flags))
                elif record.type==4:
                    batch.append(dict(type='resize',columns=event.size.x,rows=event.size.y))
            with lock: events.extend(batch)
threading.Thread(target=reader,daemon=True).start()
sys.stdout.reconfigure(encoding='utf-8')
phase=None;request={}
try:
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        request=read_snapshot(control) or request
        if request.get('stop'): break
        if request.get('phase')!=phase:
            phase=request.get('phase')
            if phase is not None:
                assert k.SetConsoleMode(stdin,input_mode|bool(request.get('processed')))
                assert k.FlushConsoleInputBuffer(stdin)
                with lock:
                    events.clear();data.clear();signals.clear()
                print(request.get('sequence','')+'\x1b]2;Nemoterm Win32 '+phase+'\x07',end='',flush=True)
        size=os.get_terminal_size()
        with lock:
            snapshot=dict(phase=phase,events=list(events),hex=data.hex(),signals=list(signals),
                          columns=size.columns,rows=size.lines,vt=vt)
        write_snapshot(report,snapshot)
        time.sleep(.025)
except Exception:
    write_snapshot(report,dict(error=traceback.format_exc(),phase=phase))
    raise
finally:
    k.SetConsoleMode(stdin,old.value)
