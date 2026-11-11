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

def capture(hwnd, name=None, return_pixels=False):
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
        return bytes(rgb) if return_pixels else hashlib.sha256(rgb).hexdigest()
    finally:
        g.SelectObject(mem, previous)
        g.DeleteObject(bitmap)
        g.DeleteDC(mem)
        u.ReleaseDC(hwnd, dc)

def scene(text, colour):
    return ('\x1b[?25l\x1b[2J\x1b[H'+text+'\r\n中文与组合字符 A\u0301\r\n' +
            '\x1b[48;2;40;80;120m'+' '*35+'\x1b[0m\r\n' +
            '\x1bP0;1q"1;1;96;36#1;2;'+colour+'#1'+('!96~-')*6+'\x1b\\')

