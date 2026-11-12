"""Real ReadFile byte reads from a private ConPTY console, with UTF-16 injection."""
import ctypes as c
from ctypes import wintypes as w
import json,os,sys,time,threading
from pathlib import Path
from fixture_io import read_snapshot,write_snapshot
report,control=map(Path,sys.argv[1:3]);chunk=int(sys.argv[3]);mode=int(sys.argv[4])
k=c.WinDLL('kernel32',use_last_error=True)
k.GetStdHandle.argtypes=[w.DWORD];k.GetStdHandle.restype=w.HANDLE
stdin=k.GetStdHandle(-10)
k.SetConsoleMode.argtypes=[w.HANDLE,w.DWORD];k.GetConsoleMode.argtypes=[w.HANDLE,c.POINTER(w.DWORD)]
k.ReadFile.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p]
k.FlushConsoleInputBuffer.argtypes=[w.HANDLE]
k.GetNumberOfConsoleInputEvents.argtypes=[w.HANDLE,c.POINTER(w.DWORD)]
class Key(c.Structure):
 _fields_=[('down',w.BOOL),('repeat',w.WORD),('vk',w.WORD),('scan',w.WORD),('character',w.WORD),('control',w.DWORD)]
class Event(c.Union):_fields_=[('key',Key),('padding',c.c_byte*16)]
class Record(c.Structure):_fields_=[('type',w.WORD),('event',Event)]
k.WriteConsoleInputW.argtypes=[w.HANDLE,c.POINTER(Record),w.DWORD,c.POINTER(w.DWORD)]
assert c.sizeof(Record)==20
old=w.DWORD();assert k.GetConsoleMode(stdin,c.byref(old));assert k.SetConsoleCP(65001);assert k.SetConsoleMode(stdin,mode)
data=bytearray();sizes=[];lock=threading.Lock();done=False;read_error=0

def reader():
 global done,read_error
 buffer=c.create_string_buffer(chunk);count=w.DWORD()
 while True:
  ok=k.ReadFile(stdin,buffer,chunk,c.byref(count),None)
  if not ok or not count.value:read_error=c.get_last_error() if not ok else 0;break
  with lock:data.extend(buffer.raw[:count.value]);sizes.append(count.value)
 done=True
threading.Thread(target=reader,daemon=True).start()
last=None;deadline=time.monotonic()+60
try:
 while time.monotonic()<deadline:
  request=read_snapshot(control)
  if request.get('stop'):break
  if request and request.get('id')!=last:
   last=request['id']
   if request.get('reset'):
    with lock:data.clear();sizes.clear()
   if request.get('flush'):assert k.FlushConsoleInputBuffer(stdin)
   units=request.get('units',[])
   if units:
    records=(Record*len(units))()
    for i,unit in enumerate(units):records[i].type=1;records[i].event.key=Key(True,1,0,0,unit,0)
    written=w.DWORD();assert k.WriteConsoleInputW(stdin,records,len(records),c.byref(written));assert written.value==len(records)
  count=w.DWORD();assert k.GetNumberOfConsoleInputEvents(stdin,c.byref(count))
  with lock:value=dict(id=last,hex=data.hex(),read_sizes=list(sizes),reader_done=done,read_error=read_error,events_pending=count.value)
  write_snapshot(report,value);time.sleep(.01)
finally:k.SetConsoleMode(stdin,old.value)
