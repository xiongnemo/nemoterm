"""Read-only failure metadata from a retained fixture-owned process.

No stack or terminal-content reads, suspension, injection or global input.
Observation errors are retained without replacing the original test failure.
"""
import ctypes as c
from ctypes import wintypes as w
from thread_snapshot import OwnedThreadSnapshot


def record_owned_failure(process, job, record, label):
    state = dict(pid=process.pid, exit_code=process.poll())
    record['process_before_cleanup'] = state
    try:
        state['job'] = job.accounting()
    except Exception as error:
        state['job_error'] = repr(error)
    if state['exit_code'] is not None:
        return
    try:
        observer = OwnedThreadSnapshot(process, job)
        state['threads'] = observer.snapshot(label)
        observer.owner._validate_owner()
        user = c.WinDLL('user32', use_last_error=True)
        callback = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        user.EnumWindows.argtypes = [callback, w.LPARAM]
        user.EnumChildWindows.argtypes = [w.HWND, callback, w.LPARAM]
        user.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
        user.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, c.c_int]
        user.GetParent.argtypes, user.GetParent.restype = [w.HWND], w.HWND
        user.IsWindowVisible.argtypes = [w.HWND]
        windows, seen = [], set()

        @callback
        def visit(hwnd, _):
            if hwnd in seen:
                return True
            seen.add(hwnd)
            owner = w.DWORD()
            user.GetWindowThreadProcessId(hwnd, c.byref(owner))
            if owner.value != process.pid:
                return True
            kind = c.create_unicode_buffer(128)
            user.GetClassNameW(hwnd, kind, len(kind))
            windows.append(dict(hwnd=hwnd, kind=kind.value,
                                parent=user.GetParent(hwnd),
                                visible=bool(user.IsWindowVisible(hwnd))))
            user.EnumChildWindows(hwnd, visit, 0)
            return True

        user.EnumWindows(visit, 0)
        state['windows'] = windows
    except Exception as error:
        state['observation_error'] = repr(error)
    state['exit_code_after_observation'] = process.poll()
