"""Read only processes whose handles belong to the fixture's private Windows job."""
import ctypes as c
from ctypes import wintypes as w
from console_process_utils import ProcessEntry
from owned_job import k  # WinDLL(use_last_error=True), including the path query

k.Process32FirstW.argtypes = k.Process32NextW.argtypes = [w.HANDLE, c.POINTER(ProcessEntry)]
k.GetProcessTimes.argtypes = [w.HANDLE] + [c.POINTER(w.FILETIME)] * 4


def job_images(job):
    unavailable = []
    handles = job.member_handles(unavailable)
    rows = {}
    try:
        for h in handles:
            pid = k.GetProcessId(h)
            row = rows[pid] = {'pid': pid}
            times = [w.FILETIME() for _ in range(4)]
            if k.GetProcessTimes(h, *(c.byref(t) for t in times)):
                row['created'] = times[0].dwLowDateTime | times[0].dwHighDateTime << 32
            else:
                row['creation_error'] = c.get_last_error()
            path = c.create_unicode_buffer(32768)
            size = w.DWORD(len(path))
            if k.QueryFullProcessImageNameW(h, 0, path, c.byref(size)):
                row['image'] = path.value
            else:
                row['image_error'] = c.get_last_error()
        if rows:
            snap = k.CreateToolhelp32Snapshot(2, 0)
            if snap == c.c_void_p(-1).value:
                unavailable.append(dict(operation='CreateToolhelp32Snapshot', winerror=c.get_last_error()))
            else:
                try:
                    entry = ProcessEntry(); entry.size = c.sizeof(entry)
                    ok = k.Process32FirstW(snap, c.byref(entry))
                    while ok:
                        if entry.pid in rows:
                            rows[entry.pid].update(name=entry.name, parent=entry.parent, threads=entry.threads)
                        ok = k.Process32NextW(snap, c.byref(entry))
                    error = c.get_last_error()
                    if error != 18:  # ERROR_NO_MORE_FILES
                        unavailable.append(dict(operation='Process32 enumeration', winerror=error))
                finally:
                    k.CloseHandle(snap)
        return dict(members=list(rows.values()), unavailable=unavailable)
    finally:
        for h in handles:
            k.CloseHandle(h)


def finish_observed(job):
    # Two seconds is still the acceptance deadline. Only after failing it do
    # we observe whether those exact handles signal without our intervention.
    return job.finish(grace=2, observe_after_deadline=16)
