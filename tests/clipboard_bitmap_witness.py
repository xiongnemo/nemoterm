"""Count first materializations of one generated CF_DIB on a hosted Windows desktop.

WM_RENDERFORMAT identifies a request for bytes, not every read or its caller.
The clipboard remains materialized until the next publication. Never read it in
this observer. The independent control at the bottom explicitly reads its own DIB.
"""
import ctypes as c
from ctypes import wintypes as w
import os
import time
from pathlib import Path
from native_test_utils import u, k, wait_for
from clipboard_test_utils import SavedClipboard
from fixture_io import write_snapshot

DIB = 8
RENDER, RENDER_ALL = 0x0305, 0x0306
UINT_PTR, LRESULT = c.c_size_t, c.c_ssize_t
SUBPROC = c.WINFUNCTYPE(LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM, UINT_PTR, UINT_PTR)
com = c.windll.comctl32
com.SetWindowSubclass.argtypes = [w.HWND, SUBPROC, UINT_PTR, UINT_PTR]
com.DefSubclassProc.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
com.DefSubclassProc.restype = LRESULT
u.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, c.c_int, c.c_int,
                              c.c_int, c.c_int, w.HWND, w.HMENU, w.HINSTANCE, c.c_void_p]
u.CreateWindowExW.restype = w.HWND
u.DestroyWindow.argtypes = [w.HWND]
u.PeekMessageW.argtypes = [c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT]
u.DispatchMessageW.argtypes = [c.POINTER(w.MSG)]
u.DispatchMessageW.restype = LRESULT
u.GetOpenClipboardWindow.restype = w.HWND
u.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
u.GetClipboardSequenceNumber.restype = w.DWORD


class BitmapWitness:
    def __init__(self, path, data):
        self.path, self.data, self.pending = path, data, False
        self.record = dict(events=[], errors=[], published_ns=None, clock='monotonic_ns')
        self.proc = SUBPROC(self.on_message)
        self.hwnd = u.CreateWindowExW(0, 'STATIC', 'Nemoterm generated bitmap owner', 0,
                                      0, 0, 1, 1, None, None, None, None)
        if not self.hwnd: raise c.WinError()
        if not com.SetWindowSubclass(self.hwnd, self.proc, 1, 0):
            u.DestroyWindow(self.hwnd)
            raise RuntimeError('Cannot subclass clipboard owner')
        self.record['owner_hwnd'] = self.hwnd

    def publish(self):
        wait_for(lambda: u.OpenClipboard(self.hwnd))
        try:
            assert u.EmptyClipboard()
            u.SetClipboardData(DIB, None)  # NULL is also the success return here.
            assert u.GetClipboardOwner() == self.hwnd and u.IsClipboardFormatAvailable(DIB)
            self.pending = True
            self.record['published_ns'] = time.monotonic_ns()
        finally:
            u.CloseClipboard()
        self.save()

    def render(self, reason):
        event = dict(ns=time.monotonic_ns(), reason=reason, supplied=False,
                     sequence=u.GetClipboardSequenceNumber())
        self.record['events'].append(event)
        # This is the HWND passed to OpenClipboard, if one was supplied. It is
        # not a call stack; a NULL value cannot identify the reader process.
        opener = u.GetOpenClipboardWindow()
        pid = w.DWORD()
        if opener: u.GetWindowThreadProcessId(opener, c.byref(pid))
        event.update(open_hwnd=opener, open_hwnd_pid=pid.value or None)
        handle = k.GlobalAlloc(2, len(self.data))
        if not handle: raise c.WinError()
        try:
            ptr = k.GlobalLock(handle)
            if not ptr: raise c.WinError()
            try: c.memmove(ptr, self.data, len(self.data))
            finally: k.GlobalUnlock(handle)
            if not u.SetClipboardData(DIB, handle): raise c.WinError()
            handle = None
            self.pending = False
            event.update(supplied=True, supplied_ns=time.monotonic_ns())
        finally:
            if handle: k.GlobalFree(handle)

    def on_message(self, hwnd, msg, wp, lp, subclass, ref):
        try:
            if msg == RENDER and wp == DIB:
                if self.pending: self.render('WM_RENDERFORMAT')
                return 0  # requester already holds the clipboard open
            if msg == RENDER_ALL:
                if self.pending and u.OpenClipboard(hwnd):
                    try:
                        if u.GetClipboardOwner() == hwnd: self.render('WM_RENDERALLFORMATS')
                    finally: u.CloseClipboard()
                return 0
        except Exception as exc:
            self.record['errors'].append(repr(exc))
            return 0
        return com.DefSubclassProc(hwnd, msg, wp, lp)

    def pump(self):
        counts = (len(self.record['events']), len(self.record['errors']))
        msg = w.MSG()
        while u.PeekMessageW(c.byref(msg), None, 0, 0, 1): u.DispatchMessageW(c.byref(msg))
        if counts != (len(self.record['events']),len(self.record['errors'])): self.save()

    def save(self):
        write_snapshot(self.path, self.record)

    def close(self):
        if not u.DestroyWindow(self.hwnd): raise c.WinError()
        self.save()


if __name__ == '__main__':
    from concurrent.futures import ThreadPoolExecutor
    from agent_clipboard_fixture import bitmap_bytes
    assert os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
    data = bitmap_bytes()
    target = Path('build/dib-witness-control.json')
    owner = BitmapWitness(target, data)
    saved = SavedClipboard(owner.hwnd)
    try:
        owner.publish()
        for _ in range(20):
            owner.pump()
            assert u.IsClipboardFormatAvailable(DIB)
            time.sleep(.01)
        assert not owner.record['events'], owner.record
        owner.record['availability_only'] = 'no materialization'
        def read_twice():
            wait_for(lambda: u.OpenClipboard(None))
            try:
                for _ in range(2):
                    handle = u.GetClipboardData(DIB)
                    assert handle and k.GlobalSize(handle) >= len(data)
                    ptr = k.GlobalLock(handle)
                    assert ptr
                    try: assert c.string_at(ptr, len(data)) == data
                    finally: k.GlobalUnlock(handle)
            finally: u.CloseClipboard()
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(read_twice)
            wait_for(lambda: (owner.pump(), future.done())[1], timeout=10)
            future.result()
        events = owner.record['events']
        assert not owner.record['errors'] and len(events) == 1 and events[0]['supplied'] and events[0]['reason'] == 'WM_RENDERFORMAT', owner.record
        owner.record['two_exact_data_reads'] = True
    finally:
        try: saved.restore()
        finally: owner.close()
