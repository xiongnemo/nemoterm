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
    selected = {root_pid}
    while True:
        more = {pid for pid, (parent, _) in rows.items() if parent in selected}
        if more <= selected: break
        selected |= more
    result = []
    for pid in selected:
        if pid not in rows: continue
        handle = k.OpenProcess(0x410, False, pid)
        if not handle: continue
        try:
            name, size = c.create_unicode_buffer(32768), w.DWORD(32768)
            if not k.QueryFullProcessImageNameW(handle, 0, name, c.byref(size)):
                continue
            result.append(dict(pid=pid, parent=rows[pid][0], path=name.value,
                               memory=memory_sample(handle)))
        finally:
            k.CloseHandle(handle)
    return result
