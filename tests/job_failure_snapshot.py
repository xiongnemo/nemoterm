"""Observe retained job members only after the original cleanup deadline failed."""
import ctypes as c
from ctypes import wintypes as w
import json
from pathlib import Path
import time

from console_process_utils import ProcessEntry, creation_time
from owned_job import k


class BorrowedProcess:
    def __init__(self, handle):
        self._handle = handle
        self.pid = k.GetProcessId(handle)

    def poll(self):
        if k.WaitForSingleObject(self._handle, 0) == 258:
            return None
        code = w.DWORD()
        if not k.GetExitCodeProcess(self._handle, c.byref(code)):
            raise c.WinError(c.get_last_error())
        return code.value


def command_line(handle):
    class UnicodeString(c.Structure):
        _fields_ = [('length', w.USHORT), ('maximum', w.USHORT), ('buffer', c.c_void_p)]
    native = c.WinDLL('ntdll')
    query = native.NtQueryInformationProcess
    query.argtypes = [w.HANDLE, w.ULONG, c.c_void_p, w.ULONG, c.POINTER(w.ULONG)]
    query.restype = w.LONG
    needed = w.ULONG()
    query(handle, 60, None, 0, c.byref(needed))
    if not c.sizeof(UnicodeString) <= needed.value <= 1024*1024:
        raise RuntimeError(('Invalid command-line buffer size', needed.value))
    buffer = c.create_string_buffer(needed.value)
    status = query(handle, 60, buffer, len(buffer), c.byref(needed))
    if status < 0:
        raise RuntimeError(('Command-line query failed', hex(status & 0xffffffff)))
    value = UnicodeString.from_buffer(buffer)
    offset = (value.buffer or 0)-c.addressof(buffer)
    if value.length % 2 or offset < c.sizeof(value) or offset+value.length > len(buffer):
        raise RuntimeError('Command line lies outside its response')
    return c.wstring_at(value.buffer, value.length//2)


def capture_job_failure(job, handles, destination, dump_helper=None):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    result = dict(after_failed_deadline=True, injected=False, processes=[])
    parents = {}
    snapshot = k.CreateToolhelp32Snapshot(2, 0)
    if snapshot == c.c_void_p(-1).value:
        raise c.WinError(c.get_last_error())
    try:
        entry = ProcessEntry(); entry.size = c.sizeof(entry)
        ok = k.Process32FirstW(snapshot, c.byref(entry))
        selected = {k.GetProcessId(h) for h in handles}
        while ok:
            if entry.pid in selected:
                parents[entry.pid] = entry.parent
            ok = k.Process32NextW(snapshot, c.byref(entry))
    finally:
        k.CloseHandle(snapshot)
    for retained in handles:
        if k.WaitForSingleObject(retained, 0) == 0:
            continue
        pid = k.GetProcessId(retained)
        record = dict(pid=pid, parent=parents.get(pid), created=creation_time(retained),
                      captured_filetime=time.time_ns()//100+116444736000000000)
        result['processes'].append(record)
        # The retained handle prevents PID reuse; additionally verify the new
        # query/VM-read handle against both creation time and private-job membership.
        handle = k.OpenProcess(0x100410, False, pid)
        try:
            member = w.BOOL()
            if not handle or creation_time(handle) != record['created'] or not k.IsProcessInJob(
                    handle, job.handle, c.byref(member)) or not member.value:
                raise RuntimeError('Retained process ownership changed')
            process = BorrowedProcess(handle)
            try:
                record['command_line'] = command_line(handle)
            except Exception as error:
                record['command_line_error'] = repr(error)
            from owned_failure_state import record_owned_failure
            record_owned_failure(process, job, record, 'post-deadline')
            if dump_helper and process.poll() is None:
                from native_failure_dump import capture_owned_failure_dump
                record['dump_capture'] = capture_owned_failure_dump(
                    dump_helper, process, job, destination/str(pid))
        except Exception as error:
            record['error'] = repr(error)
        finally:
            if handle:
                k.CloseHandle(handle)
    (destination/'snapshot.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result
