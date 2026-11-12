"""Read process metadata, returning only descendants of an owned root PID."""
from native_test_utils import c, w, k, memory_sample

class ProcessEntry(c.Structure):
    _fields_ = [('size', w.DWORD), ('usage', w.DWORD), ('pid', w.DWORD),
        ('heap', c.c_size_t), ('module', w.DWORD), ('threads', w.DWORD),
        ('parent', w.DWORD), ('priority', w.LONG), ('flags', w.DWORD),
        ('name', w.WCHAR * 260)]
k.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
k.CreateToolhelp32Snapshot.restype = w.HANDLE
k.Process32FirstW.argtypes = k.Process32NextW.argtypes = [w.HANDLE, c.POINTER(ProcessEntry)]
k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]
k.GetExitCodeProcess.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
k.GetProcessTimes.argtypes = [w.HANDLE] + [c.POINTER(w.FILETIME)] * 4

def creation_time(handle):
    times = [w.FILETIME() for _ in range(4)]
    if not k.GetProcessTimes(handle, *(c.byref(t) for t in times)):
        return None
    return times[0].dwLowDateTime | times[0].dwHighDateTime << 32

def descendant_pids(rows, root_pid, started):
    if root_pid not in rows or started(root_pid) is None:
        return set()
    selected = {root_pid}
    while True:
        more = {pid for pid, (parent, _) in rows.items()
                if parent in selected and pid not in selected
                and started(pid) is not None and started(pid) >= started(parent)}
        if not more:
            return selected
        selected |= more

def owned_processes(root_pid):
    snapshot = k.CreateToolhelp32Snapshot(2, 0)
    assert snapshot not in (None, c.c_void_p(-1).value)
    rows = {}
    try:
        item = ProcessEntry(); item.size = c.sizeof(item)
        ok = k.Process32FirstW(snapshot, c.byref(item))
        while ok:
            rows[item.pid] = (item.parent, item.name)
            ok = k.Process32NextW(snapshot, c.byref(item))
    finally:
        k.CloseHandle(snapshot)
    # A snapshot's parent PID is historical: it can name an unrelated newer
    # process after the real parent exited and Windows recycled its PID.
    created = {}
    def started(pid):
        if pid not in created:
            handle = k.OpenProcess(0x1000, False, pid)
            try:
                created[pid] = creation_time(handle) if handle else None
            finally:
                if handle: k.CloseHandle(handle)
        return created[pid]
    selected = descendant_pids(rows, root_pid, started)
    result = []
    for pid in selected:
        if pid not in rows: continue
        handle = k.OpenProcess(0x410, False, pid)
        if not handle: continue
        try:
            if creation_time(handle) != created[pid]:
                continue  # exited/reused between the snapshot and this handle
            name, size = c.create_unicode_buffer(32768), w.DWORD(32768)
            if not k.QueryFullProcessImageNameW(handle, 0, name, c.byref(size)):
                continue
            result.append(dict(pid=pid, parent=rows[pid][0], path=name.value,
                               memory=memory_sample(handle)))
        finally:
            k.CloseHandle(handle)
    return result
