"""Opt-in debugger for a newly spawned private-job fixture, never acceptance.

Inherited handles establish identity in the helper itself. Attaching a debugger
changes scheduling and exception dispatch, so this is diagnostic evidence only.
"""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import subprocess
import time

k = c.WinDLL('kernel32', use_last_error=True)
k.GetCurrentProcess.restype = w.HANDLE
k.DuplicateHandle.argtypes = [w.HANDLE, w.HANDLE, w.HANDLE, c.POINTER(w.HANDLE), w.DWORD, w.BOOL, w.DWORD]
k.IsProcessInJob.argtypes = [w.HANDLE, w.HANDLE, c.POINTER(w.BOOL)]
k.GetProcessId.argtypes = [w.HANDLE]
k.GetProcessId.restype = w.DWORD
k.CreateEventW.argtypes = [c.c_void_p, w.BOOL, w.BOOL, w.LPCWSTR]
k.CreateEventW.restype = w.HANDLE
k.SetEvent.argtypes = [w.HANDLE]
k.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
k.WaitForSingleObject.restype = w.DWORD
k.CloseHandle.argtypes = [w.HANDLE]


class NativeExceptionObserver:
    def __init__(self, executable, process, job, destination):
        executable = Path(executable).resolve(strict=True)
        self.destination = Path(destination).resolve()
        self.destination.mkdir(parents=True, exist_ok=False)
        self.helper = None
        self.events = []
        self.log = None
        member = w.BOOL()
        if (not job.handle or not k.IsProcessInJob(process._handle, job.handle, c.byref(member))
                or not member.value or k.GetProcessId(process._handle) != process.pid
                or k.WaitForSingleObject(process._handle, 0) != 258):
            raise RuntimeError('Observer requires a retained live member of this private job')
        self.identity = dict(pid=process.pid, observer=str(executable),
            observer_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
            diagnostic_only=True, scope='One live fixture process, inherited process and private-job handles')
        (self.destination/'identity.json').write_text(json.dumps(self.identity, indent=2)+'\n')
        inherited = []
        try:
            for _ in range(2):
                event = k.CreateEventW(None, True, False, None)
                if not event: raise c.WinError(c.get_last_error())
                self.events.append(event)
            current = k.GetCurrentProcess()
            for handle in (process._handle, job.handle, *self.events):
                duplicate = w.HANDLE()
                if not k.DuplicateHandle(current, handle, current, c.byref(duplicate), 0, True, 2):
                    raise c.WinError(c.get_last_error())
                inherited.append(duplicate.value)
            startup = subprocess.STARTUPINFO()
            startup.lpAttributeList = {'handle_list': inherited}
            self.log = (self.destination/'events.jsonl').open('wb')
            self.helper = subprocess.Popen([str(executable), *map(str, inherited), str(self.destination)],
                stdout=self.log, stderr=subprocess.STDOUT, startupinfo=startup, close_fds=True,
                creationflags=subprocess.CREATE_NO_WINDOW)
            deadline = time.monotonic()+15
            while True:
                state = k.WaitForSingleObject(self.events[0], 50)
                if state == 0: break
                if state != 258: raise c.WinError(c.get_last_error())
                if self.helper.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Exception observer did not complete its attach handshake')
        except BaseException:
            self.close()
            raise
        finally:
            for handle in inherited: k.CloseHandle(handle)

    def close(self):
        result = dict(self.identity)
        try:
            if self.helper is not None:
                if len(self.events) == 2: k.SetEvent(self.events[1])
                try:
                    result['exit_code'] = self.helper.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    # Only our retained helper is terminated. After the ready
                    # handshake, kill-on-exit is known disabled. Before readiness
                    # target survival is not promised; its private job owns cleanup.
                    self.helper.terminate()
                    result['exit_code'] = self.helper.wait(timeout=5)
                    result['forced_helper_cleanup'] = True
                self.helper = None
        finally:
            for event in self.events: k.CloseHandle(event)
            self.events = []
            if self.log: self.log.close(); self.log = None
        result['events_file'] = str(self.destination/'events.jsonl')
        result['dumps'] = [p.name for p in self.destination.glob('*.dmp')]
        (self.destination/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        return result
