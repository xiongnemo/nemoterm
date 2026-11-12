"""Bound the lifetime of a newly spawned Windows test process and its children.

The root starts suspended, joins a private unnamed job, then resumes. No PID
search is used to terminate processes. Working-set, CPU and UI limits are unset.
https://learn.microsoft.com/windows/win32/procthread/job-objects
"""
import ctypes as c
from ctypes import wintypes as w
import subprocess
import time

k = c.WinDLL('kernel32', use_last_error=True)


class BasicLimits(c.Structure):
    _fields_ = [('process_time', c.c_int64), ('job_time', c.c_int64),
        ('flags', w.DWORD), ('min_ws', c.c_size_t), ('max_ws', c.c_size_t),
        ('active_limit', w.DWORD), ('affinity', c.c_size_t),
        ('priority', w.DWORD), ('scheduling', w.DWORD)]


class ExtendedLimits(c.Structure):
    _fields_ = [('basic', BasicLimits), ('io', c.c_uint64 * 6),
        ('process_memory', c.c_size_t), ('job_memory', c.c_size_t),
        ('peak_process_memory', c.c_size_t), ('peak_job_memory', c.c_size_t)]


class Accounting(c.Structure):
    _fields_ = [('times', c.c_int64 * 4), ('faults', w.DWORD),
        ('total', w.DWORD), ('active', w.DWORD), ('terminated', w.DWORD)]


class ThreadEntry(c.Structure):
    _fields_ = [('size', w.DWORD), ('usage', w.DWORD), ('tid', w.DWORD),
        ('pid', w.DWORD), ('base_priority', w.LONG), ('delta_priority', w.LONG),
        ('flags', w.DWORD)]


k.CreateJobObjectW.argtypes, k.CreateJobObjectW.restype = [c.c_void_p, w.LPCWSTR], w.HANDLE
k.SetInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]
k.QueryInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p]
k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
k.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
k.CloseHandle.argtypes = [w.HANDLE]
k.CreateToolhelp32Snapshot.argtypes, k.CreateToolhelp32Snapshot.restype = [w.DWORD, w.DWORD], w.HANDLE
k.Thread32First.argtypes = k.Thread32Next.argtypes = [w.HANDLE, c.POINTER(ThreadEntry)]
k.OpenThread.argtypes, k.OpenThread.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
k.ResumeThread.argtypes, k.ResumeThread.restype = [w.HANDLE], w.DWORD
k.OpenProcess.argtypes, k.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
k.IsProcessInJob.argtypes = [w.HANDLE, w.HANDLE, c.POINTER(w.BOOL)]
k.WaitForSingleObject.argtypes, k.WaitForSingleObject.restype = [w.HANDLE, w.DWORD], w.DWORD


def resume_initial_thread(pid):
    snapshot = k.CreateToolhelp32Snapshot(4, 0)  # TH32CS_SNAPTHREAD
    if snapshot == c.c_void_p(-1).value:
        raise c.WinError(c.get_last_error())
    tids = []
    try:
        entry = ThreadEntry(); entry.size = c.sizeof(entry)
        ok = k.Thread32First(snapshot, c.byref(entry))
        while ok:
            if entry.pid == pid:
                tids.append(entry.tid)
            ok = k.Thread32Next(snapshot, c.byref(entry))
    finally:
        k.CloseHandle(snapshot)
    if len(tids) != 1:
        raise RuntimeError(('Suspended fixture must have exactly one initial thread', pid, tids))
    thread = k.OpenThread(2, False, tids[0])  # THREAD_SUSPEND_RESUME
    if not thread:
        raise c.WinError(c.get_last_error())
    try:
        previous = k.ResumeThread(thread)
        if previous != 1:
            raise RuntimeError(('Unexpected initial suspension count', previous))
    finally:
        k.CloseHandle(thread)


class OwnedJob:
    def __init__(self):
        self.handle = k.CreateJobObjectW(None, None)
        if not self.handle:
            raise c.WinError(c.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE only
        if not k.SetInformationJobObject(self.handle, 9, c.byref(limits), c.sizeof(limits)):
            error = c.get_last_error()
            k.CloseHandle(self.handle); self.handle = None
            raise c.WinError(error)
        self.cleanup = None

    def spawn(self, args, **kwargs):
        if not self.handle:
            raise RuntimeError('Job is closed')
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | 4  # CREATE_SUSPENDED
        process = subprocess.Popen(args, **kwargs)
        try:
            if not k.AssignProcessToJobObject(self.handle, int(process._handle)):
                raise c.WinError(c.get_last_error())
            resume_initial_thread(process.pid)
        except BaseException:
            process.terminate(); process.wait(timeout=5)
            raise
        return process

    def accounting(self):
        value = Accounting()
        if not k.QueryInformationJobObject(self.handle, 1, c.byref(value), c.sizeof(value), None):
            raise c.WinError(c.get_last_error())
        return dict(total=value.total, active=value.active, terminated=value.terminated)

    def member_handles(self):
        # Membership is queried from the private job, not historical parent IDs.
        capacity = 32
        while capacity <= 4096:
            raw = c.create_string_buffer(8+capacity*c.sizeof(c.c_size_t))
            if k.QueryInformationJobObject(self.handle, 3, raw, len(raw), None):
                count = w.DWORD.from_buffer(raw, 4).value
                ids = (c.c_size_t*count).from_buffer(raw, 8)
                break
            error = c.get_last_error()
            if error != 234:  # ERROR_MORE_DATA
                raise c.WinError(error)
            capacity *= 2
        else:
            raise RuntimeError('Owned fixture exceeded 4096 job members')
        handles = []
        for pid in ids:
            handle = k.OpenProcess(0x101000, False, pid)  # synchronize, query limited
            if not handle:
                continue  # a short-lived child may have exited meanwhile
            member = w.BOOL()
            if k.IsProcessInJob(handle, self.handle, c.byref(member)) and member.value:
                handles.append(handle)
            else:
                k.CloseHandle(handle)
        return handles

    def finish(self, grace=2):
        if self.cleanup is not None:
            return self.cleanup
        deadline = time.monotonic()+grace
        while (before := self.accounting())['active'] and time.monotonic() < deadline:
            time.sleep(.02)
        forced = before['active'] > 0
        handles = self.member_handles()
        try:
            if forced and not k.TerminateJobObject(self.handle, 1):
                raise c.WinError(c.get_last_error())
            deadline = time.monotonic()+5
            for handle in handles:
                remaining = max(0, int((deadline-time.monotonic())*1000))
                if k.WaitForSingleObject(handle, remaining) != 0:
                    raise RuntimeError('Terminated owned process did not signal exit')
            while (after := self.accounting())['active'] and time.monotonic() < deadline:
                time.sleep(.02)
            if after['active']:
                raise RuntimeError(('Owned job did not drain', before, after))
        finally:
            for handle in handles:
                k.CloseHandle(handle)
        self.cleanup = dict(before=before, after=after, terminated_remaining=forced)
        return self.cleanup

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        try:
            self.finish()
        finally:
            k.CloseHandle(self.handle)
            self.handle = None
