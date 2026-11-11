"""Pixel and working-set checks on a newly spawned Nemoterm/ConPTY window."""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import mmap
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import threading
import time
import zlib
from fixture_io import read_snapshot, write_snapshot

root = Path(__file__).resolve().parent.parent
u, g, k, ps = c.windll.user32, c.windll.gdi32, c.windll.kernel32, c.windll.psapi
u.SetProcessDPIAware()
u.GetDC.argtypes, u.GetDC.restype = [w.HWND], w.HDC
u.ReleaseDC.argtypes = [w.HWND, w.HDC]
u.PrintWindow.argtypes = [w.HWND, w.HDC, w.UINT]
u.MoveWindow.argtypes = [w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.BOOL]
u.SendMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
g.CreateCompatibleDC.argtypes, g.CreateCompatibleDC.restype = [w.HDC], w.HDC
g.CreateDIBSection.argtypes = [w.HDC, c.c_void_p, w.UINT,
                              c.POINTER(c.c_void_p), w.HANDLE, w.DWORD]
g.CreateDIBSection.restype = w.HBITMAP
g.SelectObject.argtypes, g.SelectObject.restype = [w.HDC, w.HGDIOBJ], w.HGDIOBJ
g.DeleteObject.argtypes, g.DeleteDC.argtypes = [w.HGDIOBJ], [w.HDC]
k.OpenProcess.argtypes, k.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
k.CloseHandle.argtypes = [w.HANDLE]
ps.QueryWorkingSet.argtypes = [w.HANDLE, c.c_void_p, w.DWORD]
ps.GetProcessMemoryInfo.argtypes = [w.HANDLE, c.c_void_p, w.DWORD]

class Counters(c.Structure):
    _fields_ = [('cb', w.DWORD), ('faults', w.DWORD)] + [
        (name, c.c_size_t) for name in ('peak_ws', 'ws', 'peak_paged', 'paged',
            'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile', 'private')]

def memory_sample(handle):
    # PSAPI_WORKING_SET_BLOCK.Shared is bit 8; non-sharable resident pages
    # give private WS. Never trim the working set to improve the measurement.
    # https://learn.microsoft.com/windows/win32/api/psapi/ns-psapi-psapi_working_set_block
    pages = (c.c_size_t * 65537)()
    if not ps.QueryWorkingSet(handle, pages, c.sizeof(pages)):
        raise c.WinError()
    count = pages[0]
    counters = Counters()
    counters.cb = c.sizeof(counters)
    if not ps.GetProcessMemoryInfo(handle, c.byref(counters), counters.cb):
        raise c.WinError()
    return {'private_ws': sum(not (pages[i+1] & 256) for i in range(count))*mmap.PAGESIZE,
            'total_ws': count*mmap.PAGESIZE, 'private_commit': counters.private}

def find_window(pid):
    matches = []
    @c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def visit(hwnd, _):
        owner, cls = w.DWORD(), c.create_unicode_buffer(128)
        u.GetWindowThreadProcessId(hwnd, c.byref(owner))
        u.GetClassNameW(hwnd, cls, 128)
        if owner.value == pid and cls.value == 'Nemoterm' and u.IsWindowVisible(hwnd):
            matches.append(hwnd)
        return True
    u.EnumWindows(visit, 0)
    return matches[0] if len(matches) == 1 else None

def wait_for(fn, timeout=8):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        result = fn()
        if result:
            return result
        time.sleep(0.015)
    raise AssertionError('Timed out waiting for native fixture')

def capture(hwnd, name=None):
    rect = w.RECT()
    u.GetClientRect(hwnd, c.byref(rect))
    width, height = rect.right, rect.bottom
    info = c.create_string_buffer(struct.pack('<IiiHHIIiiII', 40, width, -height,
                                               1, 32, 0, width*height*4, 0, 0, 0, 0))
    dc = u.GetDC(hwnd)
    mem = g.CreateCompatibleDC(dc)
    bits = c.c_void_p()
    bitmap = g.CreateDIBSection(dc, info, 0, c.byref(bits), None, 0)
    if not bitmap:
        raise c.WinError()
    previous = g.SelectObject(mem, bitmap)
    try:
        if not u.PrintWindow(hwnd, mem, 3):
            raise c.WinError()
        g.GdiFlush()
        pixels = c.string_at(bits, width*height*4)
        rgb = bytearray(width*height*3)
        rgb[0::3], rgb[1::3], rgb[2::3] = pixels[2::4], pixels[1::4], pixels[0::4]
        if name:
            scanlines = b''.join(b'\0'+rgb[y*width*3:(y+1)*width*3] for y in range(height))
            def chunk(kind, data):
                return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data))
            (root/'research'/name).write_bytes(b'\x89PNG\r\n\x1a\n' +
                chunk(b'IHDR', struct.pack('>IIBBBBB', width,height,8,2,0,0,0)) +
                chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b''))
        return hashlib.sha256(rgb).hexdigest()
    finally:
        g.SelectObject(mem, previous)
        g.DeleteObject(bitmap)
        g.DeleteDC(mem)
        u.ReleaseDC(hwnd, dc)

def scene(text, colour):
    return ('\x1b[?25l\x1b[2J\x1b[H'+text+'\r\n中文与组合字符 A\u0301\r\n' +
            '\x1b[48;2;40;80;120m'+' '*35+'\x1b[0m\r\n' +
            '\x1bP0;1q"1;1;96;36#1;2;'+colour+'#1'+('!96~-')*6+'\x1b\\')

with tempfile.TemporaryDirectory(prefix='nemoterm-sync-') as directory:
    directory = Path(directory)
    report, control = directory/'report.json', directory/'control.json'
    process = subprocess.Popen([str(root/'dist/nemoterm.exe'), '--cols', '80', '--rows', '24',
        '-e', sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control)],
        env=dict(os.environ, NEMOTERM_CONPTY='bundled'), creationflags=subprocess.CREATE_NO_WINDOW)
    handle = k.OpenProcess(0x410, False, process.pid)
    samples, stop = [], threading.Event()
    def sample_memory():
        while not stop.is_set():
            try:
                samples.append(memory_sample(handle))
            except OSError:
                pass
            stop.wait(0.025)
    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    evidence = {}
    def current():
        value = read_snapshot(report)
        if value.get('error') or process.poll() is not None:
            raise AssertionError(value)
        return value
    def phase(name, sequence, expected):
        write_snapshot(control, {'phase':name, 'sequence':sequence+'\x1b[?2026$p'})
        reply = f'\x1b[?2026;{expected}$y'.encode()
        return wait_for(lambda: current() if current().get('phase') == name and
                        reply in bytes.fromhex(current().get('hex', '')) else None)
    try:
        hwnd = wait_for(lambda: find_window(process.pid))
        wait_for(current)
        phase('old', scene('SYNCHRONIZED OUTPUT: OLD FRAME', '100;0;0'), 2)
        time.sleep(0.08)
        before = capture(hwnd, 'sync-before.png')
        phase('frozen', '\x1b[?2026h'+scene('SYNCHRONIZED OUTPUT: NEW FRAME', '0;0;100')+
              '\x1b]11;rgb:18/24/30\x07', 1)
        frozen = capture(hwnd, 'sync-frozen.png')
        assert before == frozen, (before, frozen)
        u.SendMessageW(hwnd, 0x102, ord('x'), 1)
        wait_for(lambda: b'x' in bytes.fromhex(current().get('hex', '')))
        phase('commit', '\x1b[?2026l', 2)
        time.sleep(0.08)
        after = capture(hwnd, 'sync-after.png')
        assert after != before
        evidence.update(before=before, during=frozen, after=after)
        phase('timeout-start', '\x1b[?2026h'+scene('TIMEOUT RELEASED THIS FRAME', '0;100;0'), 1)
        assert capture(hwnd) == after
        time.sleep(1.15)
        phase('timeout-query', '', 2)
        assert capture(hwnd) != after
        phase('resize-start', '\x1b[?2026h', 1)
        assert u.MoveWindow(hwnd, 30, 30, 1000, 700, True)
        phase('resize-query', '', 2)
        # A large viewport checks the bounded snapshot path, including text and Sixel.
        assert u.MoveWindow(hwnd, 30, 30, 3840, 2160, True)
        large = phase('large-frame', scene('LARGE VIEWPORT MEMORY PROBE', '60;30;90'), 2)
        rect = w.RECT()
        u.GetClientRect(hwnd, c.byref(rect))
        evidence['large_viewport'] = {'width':rect.right, 'height':rect.bottom,
                                      'columns':large['columns'], 'rows':large['rows']}
        # Windows may cap this to the connected monitor. Record the measured
        # extent; the separate offscreen snapshot test covers full 3840x2160.
        assert large['columns'] > 80 and large['rows'] > 24, evidence['large_viewport']
        phase('large-freeze', '\x1b[?2026h', 1)
        evidence['large_viewport_memory'] = memory_sample(handle)
        phase('large-release', '\x1b[?2026l', 2)
        evidence['samples'] = samples
        evidence['peak_private_ws'] = max(s['private_ws'] for s in samples)
        evidence['peak_total_ws'] = max(s['total_ws'] for s in samples)
        evidence['executable_sha256'] = hashlib.sha256((root/'dist/nemoterm.exe').read_bytes()).hexdigest()
        (root/'research/sync-window-observed.json').write_text(json.dumps(evidence, indent=2))
        assert evidence['peak_private_ws'] < 20_000_000, evidence['peak_private_ws']
        print('Synchronized pixels/input/timeout/resize passed; private WS peak:',
              evidence['peak_private_ws'], 'total WS peak:', evidence['peak_total_ws'])
    finally:
        stop.set()
        sampler.join(2)
        k.CloseHandle(handle)
        write_snapshot(control, {'stop': True})
        process.wait(timeout=10)
