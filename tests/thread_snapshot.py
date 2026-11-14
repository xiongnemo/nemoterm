"""Read-only thread metadata for a retained, freshly spawned owned process.

No suspension, injection, stack reads or target calls. Thread IDs are paired
with creation times; opened handles are checked against the owning process.
NtQueryInformationThread is dynamically loaded and used only by this observer:
https://learn.microsoft.com/windows/win32/api/winternl/nf-winternl-ntqueryinformationthread
"""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
import time
from owned_job import ThreadEntry
from handle_snapshot import OwnedHandleSnapshot

k=c.WinDLL('kernel32',use_last_error=True)
n=c.WinDLL('ntdll')
k.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD];k.CreateToolhelp32Snapshot.restype=w.HANDLE
k.Thread32First.argtypes=k.Thread32Next.argtypes=[w.HANDLE,c.POINTER(ThreadEntry)]
k.OpenThread.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenThread.restype=w.HANDLE
k.CloseHandle.argtypes=[w.HANDLE]
k.GetProcessIdOfThread.argtypes=[w.HANDLE];k.GetProcessIdOfThread.restype=w.DWORD
k.GetThreadTimes.argtypes=[w.HANDLE]+[c.POINTER(w.FILETIME)]*4
k.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];k.WaitForSingleObject.restype=w.DWORD
k.GetThreadIOPendingFlag.argtypes=[w.HANDLE,c.POINTER(w.BOOL)]
n.NtQueryInformationThread.argtypes=[w.HANDLE,w.ULONG,c.c_void_p,w.ULONG,c.POINTER(w.ULONG)]
n.NtQueryInformationThread.restype=w.LONG

class ModuleInfo(c.Structure):
    _fields_=[('base',c.c_void_p),('size',w.DWORD),('entry',c.c_void_p)]
k.K32EnumProcessModulesEx.argtypes=[w.HANDLE,c.POINTER(w.HMODULE),w.DWORD,c.POINTER(w.DWORD),w.DWORD]
k.K32GetModuleInformation.argtypes=[w.HANDLE,w.HMODULE,c.POINTER(ModuleInfo),w.DWORD]
k.K32GetModuleFileNameExW.argtypes=[w.HANDLE,w.HMODULE,w.LPWSTR,w.DWORD]

def modules(handle):
    buffer=(w.HMODULE*2048)();needed=w.DWORD()
    if not k.K32EnumProcessModulesEx(handle,buffer,c.sizeof(buffer),c.byref(needed),3):
        raise c.WinError(c.get_last_error())
    if needed.value>c.sizeof(buffer) or needed.value%c.sizeof(w.HMODULE):
        raise RuntimeError('Module catalogue exceeds the bounded buffer')
    result=[]
    for module in buffer[:needed.value//c.sizeof(w.HMODULE)]:
        info=ModuleInfo();path=c.create_unicode_buffer(32768)
        if not k.K32GetModuleInformation(handle,module,c.byref(info),c.sizeof(info)):
            raise c.WinError(c.get_last_error())
        count=k.K32GetModuleFileNameExW(handle,module,path,len(path))
        if not count or count>=len(path):raise RuntimeError('Module filename unavailable or truncated')
        result.append(dict(base=info.base,size=info.size,path=path.value,name=Path(path.value).name))
    return result

class OwnedThreadSnapshot:
    def __init__(self,process,job):
        self.owner=OwnedHandleSnapshot(process,job)
        if c.sizeof(c.c_void_p)!=8:raise RuntimeError('Only Windows x64 is validated')

    def snapshot(self,label):
        self.owner._validate_owner();started=time.monotonic();pid=self.owner.process.pid
        snapshot=k.CreateToolhelp32Snapshot(4,0)
        if snapshot==c.c_void_p(-1).value:raise c.WinError(c.get_last_error())
        ids=[]
        try:
            entry=ThreadEntry();entry.size=c.sizeof(entry)
            ok=k.Thread32First(snapshot,c.byref(entry))
            while ok:
                if entry.pid==pid:ids.append(entry.tid)
                if len(ids)>1024:raise RuntimeError('Owned thread count exceeds 1024')
                ok=k.Thread32Next(snapshot,c.byref(entry))
            error=c.get_last_error()
            if error!=18:raise c.WinError(error) # ERROR_NO_MORE_FILES
        finally:k.CloseHandle(snapshot)
        threads=[];unavailable=[]
        for tid in ids:
            thread=k.OpenThread(0x100040,False,tid) # SYNCHRONIZE | THREAD_QUERY_INFORMATION
            if not thread:
                error=c.get_last_error()
                if error==87:unavailable.append(dict(tid=tid,reason='exited before open'));continue
                raise c.WinError(error)
            try:
                owner=k.GetProcessIdOfThread(thread)
                if owner!=pid:
                    if not owner:raise c.WinError(c.get_last_error())
                    unavailable.append(dict(tid=tid,reason='ID reused by another process'));continue
                times=[w.FILETIME() for _ in range(4)]
                if not k.GetThreadTimes(thread,*(c.byref(t) for t in times)):raise c.WinError(c.get_last_error())
                state=k.WaitForSingleObject(thread,0)
                if state not in (0,258):raise c.WinError(c.get_last_error())
                address=c.c_void_p();length=w.ULONG()
                status=n.NtQueryInformationThread(thread,9,c.byref(address),c.sizeof(address),c.byref(length))
                if status<0:raise RuntimeError(('Thread start query failed',tid,hex(status&0xffffffff)))
                pending=w.BOOL()
                if not k.GetThreadIOPendingFlag(thread,c.byref(pending)):raise c.WinError(c.get_last_error())
                threads.append(dict(tid=tid,created=times[0].dwLowDateTime|(times[0].dwHighDateTime<<32),
                    exited=state==0,start=address.value,io_pending=bool(pending.value)))
            finally:k.CloseHandle(thread)
        catalogue=modules(self.owner.handle)
        for thread in threads:
            match=next((m for m in catalogue if thread['start'] is not None and m['base']<=thread['start']<m['base']+m['size']),None)
            if match:thread.update(module=match['name'],rva=thread['start']-match['base'])
        self.owner._validate_owner()
        return dict(label=label,pid=pid,threads=threads,unavailable=unavailable,modules=catalogue,
                    seconds=time.monotonic()-started,injected=False,
                    caveat='Sequential metadata; module/start addresses do not identify ownership of OS handles')
