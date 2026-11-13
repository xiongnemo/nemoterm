"""Bounded handle-type snapshots of an explicitly owned Windows x64 process.

Uses NT process-local metadata, not the system-wide handle table. Object type
names come from the OS type catalogue; no object names or payloads are queried.
Native ABI reference (Windows 8+ / TypeIndex since Windows 8.1):
https://github.com/winsiderss/phnt/tree/53fbbdc5b5d2b08761db1c7b26bfa8c820924356
This is diagnostic tooling, not a supported terminal runtime dependency.
"""
import collections
import ctypes as c
from ctypes import wintypes as w
import time

k=c.WinDLL('kernel32',use_last_error=True)
n=c.WinDLL('ntdll')
k.GetProcessId.argtypes=[w.HANDLE];k.GetProcessId.restype=w.DWORD
k.GetProcessHandleCount.argtypes=[w.HANDLE,c.POINTER(w.DWORD)]
k.IsProcessInJob.argtypes=[w.HANDLE,w.HANDLE,c.POINTER(w.BOOL)]
k.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];k.WaitForSingleObject.restype=w.DWORD
n.NtQueryInformationProcess.argtypes=[w.HANDLE,w.ULONG,c.c_void_p,w.ULONG,c.POINTER(w.ULONG)]
n.NtQueryInformationProcess.restype=w.LONG
n.NtQueryObject.argtypes=[w.HANDLE,w.ULONG,c.c_void_p,w.ULONG,c.POINTER(w.ULONG)]
n.NtQueryObject.restype=w.LONG

class UnicodeString(c.Structure):
    _fields_=[('length',w.USHORT),('maximum',w.USHORT),('buffer',c.c_void_p)]

class ObjectType(c.Structure):
    _fields_=[('name',UnicodeString),('counts',w.ULONG*12),('invalid_attributes',w.ULONG),
              ('mapping',w.ULONG*4),('access',w.ULONG),('security_required',w.BYTE),
              ('maintain_count',w.BYTE),('index',w.BYTE),('reserved',w.BYTE),
              ('pool',w.ULONG),('paged_charge',w.ULONG),('nonpaged_charge',w.ULONG)]

class HandleEntry(c.Structure):
    _fields_=[('handle',w.HANDLE),('handle_count',c.c_size_t),('pointer_count',c.c_size_t),
              ('access',w.ULONG),('type_index',w.ULONG),('attributes',w.ULONG),('reserved',w.ULONG)]

def _query(function,handle,kind,initial=4096):
    size=initial
    for _ in range(8):
        if size>4*1024*1024:raise RuntimeError('Handle metadata buffer exceeds 4 MiB')
        data=c.create_string_buffer(size);needed=w.ULONG()
        status=function(handle,kind,data,size,c.byref(needed)) & 0xffffffff
        if status==0:
            if needed.value>size:raise RuntimeError('Native metadata result exceeds buffer')
            return data,needed.value or size
        if status not in (0xc0000004,0xc0000023,0x80000005):
            raise RuntimeError(('Native metadata query failed',kind,hex(status)))
        size=max(size*2,needed.value)
    raise RuntimeError('Handle metadata query did not converge')

def object_types():
    if c.sizeof(c.c_void_p)!=8 or c.sizeof(ObjectType)!=104 or c.sizeof(HandleEntry)!=40:
        raise RuntimeError('Handle observer supports the verified Windows x64 layout only')
    data,length=_query(n.NtQueryObject,None,3)
    count=w.ULONG.from_buffer(data).value
    if not 0<count<=256:raise RuntimeError(('Invalid object type count',count))
    offset=8;result={};start=c.addressof(data)
    for _ in range(count):
        if offset+c.sizeof(ObjectType)>length:raise RuntimeError('Truncated object type record')
        info=ObjectType.from_buffer(data,offset);name=info.name
        if name.length%2 or name.length>name.maximum or not name.buffer:
            raise RuntimeError('Invalid object type name length')
        name_start=name.buffer-start
        if name_start<offset+c.sizeof(ObjectType) or name_start+name.maximum>length:
            raise RuntimeError('Object type name points outside its response')
        value=c.wstring_at(name.buffer,name.length//2)
        if not info.index or info.index in result:raise RuntimeError('Invalid or repeated object type index')
        result[info.index]=value
        offset=(name_start+name.maximum+7)&~7
    return result

class OwnedHandleSnapshot:
    def __init__(self,process,job):
        # Retain the actual Popen object/handle from OwnedJob.spawn. Never open
        # a historical PID or search the user's running processes.
        self.process=process;self.job=job;self.handle=int(process._handle)
        self._validate_owner()
        self.types=object_types()

    def _validate_owner(self):
        if not self.job.handle:raise RuntimeError('Owned job is closed')
        member=w.BOOL()
        if not k.IsProcessInJob(self.handle,self.job.handle,c.byref(member)) or not member.value:
            raise RuntimeError('Process does not belong to the supplied owned job')
        if k.GetProcessId(self.handle)!=self.process.pid:raise RuntimeError('Retained process identity mismatch')
        if k.WaitForSingleObject(self.handle,0)!=258:raise RuntimeError('Owned process is no longer running')

    def snapshot(self,label):
        self._validate_owner();started=time.monotonic()
        before=w.DWORD();after=w.DWORD()
        if not k.GetProcessHandleCount(self.handle,c.byref(before)):raise c.WinError(c.get_last_error())
        data,length=_query(n.NtQueryInformationProcess,self.handle,51)
        count=c.c_size_t.from_buffer(data).value
        if count>65536 or 16+count*c.sizeof(HandleEntry)>length:
            raise RuntimeError(('Invalid process handle snapshot length',count,length))
        entries=[]
        for index in range(count):
            e=HandleEntry.from_buffer(data,16+index*c.sizeof(HandleEntry))
            if e.type_index not in self.types:raise RuntimeError(('Unresolved object type',e.type_index))
            entries.append(dict(handle=int(e.handle or 0),type_index=e.type_index,type=self.types[e.type_index],
                                access=e.access,attributes=e.attributes))
        if len({e['handle'] for e in entries})!=count:raise RuntimeError('Duplicate values in handle snapshot')
        if not k.GetProcessHandleCount(self.handle,c.byref(after)):raise c.WinError(c.get_last_error())
        return dict(label=label,pid=self.process.pid,count=count,counts=dict(sorted(collections.Counter(e['type'] for e in entries).items())),
                    public_count_before=before.value,public_count_after=after.value,seconds=time.monotonic()-started,entries=entries,
                    injected=False,object_names_read=False,payloads_read=False,
                    caveat='Counts are sequential samples. Reused handle values do not identify the same object across snapshots.')

def compare(before,after):
    old={e['handle']:e for e in before['entries']};new={e['handle']:e for e in after['entries']}
    types=before['counts'].keys()|after['counts'].keys()
    return dict(count_delta=after['count']-before['count'],
                type_deltas={t:after['counts'].get(t,0)-before['counts'].get(t,0) for t in sorted(types)
                             if after['counts'].get(t,0)!=before['counts'].get(t,0)},
                added_values=[new[h] for h in sorted(new.keys()-old.keys())],
                removed_values=[old[h] for h in sorted(old.keys()-new.keys())],
                changed_type_at_same_value=[dict(before=old[h],after=new[h]) for h in sorted(old.keys()&new.keys())
                                           if old[h]['type_index']!=new[h]['type_index']])
