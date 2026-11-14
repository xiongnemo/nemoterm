"""Opt-in read-only code/liveness snapshots around fixture hook detachment.

Only the verified, job-owned host's executable window-procedure entry is read.
No target calls, writes, suspension, terminal contents or behavior changes.
"""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
import time
from thread_snapshot import OwnedThreadSnapshot, modules


class TabProbeBoundary:
    def __init__(self, process, job, host, initial):
        self.process, self.host = process, host
        self.owner = OwnedThreadSnapshot(process, job).owner
        self.started = time.monotonic()
        self.address = int(initial['address'],16)
        self.original = bytes(initial['bytes'])
        if len(self.original) != 32:
            raise ValueError('Incomplete baseline from the existing hover probe')
        self.module = next((m for m in modules(process._handle)
                            if m['base'] <= self.address and self.address+32 <= m['base']+m['size']), None)
        if not self.module or Path(self.module['name']).name.lower() != 'nemoterm.exe':
            raise RuntimeError('Host procedure is outside the owned executable')
        self.user = c.WinDLL('user32', use_last_error=True)
        self.kernel = c.WinDLL('kernel32', use_last_error=True)
        self.user.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
        self.kernel.ReadProcessMemory.argtypes = [w.HANDLE, c.c_void_p, c.c_void_p,
                                                  c.c_size_t, c.POINTER(c.c_size_t)]

    def snapshot(self, label):
        row = dict(label=label, seconds=time.monotonic()-self.started,
                   pid=self.process.pid, exit_code=self.process.poll())
        if row['exit_code'] is not None:
            return row
        try:
            self.owner._validate_owner()
            pid = w.DWORD()
            thread = self.user.GetWindowThreadProcessId(self.host, c.byref(pid))
            if not thread or pid.value != self.process.pid:
                raise RuntimeError('Host window is no longer owned by the retained process')
            data, read = c.create_string_buffer(32), c.c_size_t()
            if not self.kernel.ReadProcessMemory(self.process._handle, self.address, data, 32, c.byref(read)):
                raise c.WinError(c.get_last_error())
            if read.value != 32:
                raise RuntimeError('Incomplete procedure-entry observation')
            row.update(thread=thread, address=self.address, module=self.module['name'],
                       module_offset=self.address-self.module['base'], entry_hex=data.raw.hex())
            row['matches_initial_entry'] = self.original == data.raw
        except Exception as error:
            row['observation_error'] = repr(error)
        row['exit_code_after_observation'] = self.process.poll()
        return row
