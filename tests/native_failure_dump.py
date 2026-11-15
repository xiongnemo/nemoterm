"""Optional diagnostic capture after a fixture has already failed.

The helper validates inherited process/job handles itself. A second private job
bounds the helper even if the controller watchdog exits. Capture can affect
scheduling; it never converts a timeout to success or extends its deadline.
"""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import subprocess
import time
from owned_job import OwnedJob, k

k.GetCurrentProcess.restype = w.HANDLE
k.DuplicateHandle.argtypes = [w.HANDLE, w.HANDLE, w.HANDLE, c.POINTER(w.HANDLE),
                             w.DWORD, w.BOOL, w.DWORD]


def capture_owned_failure_dump(executable, process, job, destination):
    executable = Path(executable).resolve(strict=True)
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    record = dict(pid=process.pid, helper=str(executable), diagnostic_only=True,
                  helper_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
                  full_memory=False, debugger_attached=False)
    inherited = []
    started = time.monotonic()
    try:
        current = k.GetCurrentProcess()
        for handle in (process._handle, job.handle):
            duplicate = w.HANDLE()
            if not k.DuplicateHandle(current, handle, current, c.byref(duplicate), 0, True, 2):
                raise c.WinError(c.get_last_error())
            inherited.append(duplicate.value)
        startup = subprocess.STARTUPINFO()
        startup.lpAttributeList = {'handle_list': inherited}
        with (destination/'helper.jsonl').open('wb') as log, OwnedJob() as helper_job:
            helper = helper_job.spawn([str(executable), *map(str, inherited),
                str(destination/'failure.dmp')], stdout=log, stderr=subprocess.STDOUT,
                startupinfo=startup, close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                record['exit_code'] = helper.wait(timeout=10)
            except subprocess.TimeoutExpired:
                record['helper_timeout'] = True
            finally:
                record['helper_cleanup'] = helper_job.finish(
                    grace=0 if record.get('helper_timeout') else 2)
                helper.wait(timeout=5)
        dump = destination/'failure.dmp'
        if dump.exists():
            raw = dump.read_bytes()
            record['dump'] = dict(path=str(dump), bytes=len(raw),
                                  sha256=hashlib.sha256(raw).hexdigest())
    except Exception as error:
        record['error'] = repr(error)
    finally:
        for handle in inherited: k.CloseHandle(handle)
        record['seconds'] = time.monotonic()-started
        record['target_exit_after_capture'] = process.poll()
        (destination/'result.json').write_text(json.dumps(record, indent=2)+'\n')
    return record
