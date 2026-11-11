"""Capture only the Nemoterm window owned by the explicitly supplied test PID.

Fallback for the unavailable Computer Use native pipe. No input is injected.
"""
import ctypes as c
from ctypes import wintypes as w
import json
from pathlib import Path
import struct
import sys
import zlib

u, g = c.windll.user32, c.windll.gdi32
u.GetWindowDC.argtypes = [w.HWND]
u.GetWindowDC.restype = w.HDC
g.CreateCompatibleDC.argtypes = [w.HDC]
g.CreateCompatibleDC.restype = w.HDC
g.CreateCompatibleBitmap.argtypes = [w.HDC, c.c_int, c.c_int]
g.CreateCompatibleBitmap.restype = w.HBITMAP
g.SelectObject.argtypes = [w.HDC, w.HGDIOBJ]
g.SelectObject.restype = w.HGDIOBJ
g.DeleteObject.argtypes = [w.HGDIOBJ]
g.DeleteDC.argtypes = [w.HDC]
u.ReleaseDC.argtypes = [w.HWND, w.HDC]
u.PrintWindow.argtypes = [w.HWND, w.HDC, w.UINT]
g.GetDIBits.argtypes = [w.HDC, w.HBITMAP, w.UINT, w.UINT, c.c_void_p, c.c_void_p, w.UINT]
u.SetProcessDPIAware()
pid = int(sys.argv[1])
matches = []
@c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
def visit(hwnd, _):
    owner = w.DWORD()
    u.GetWindowThreadProcessId(hwnd, c.byref(owner))
    if owner.value == pid and u.IsWindowVisible(hwnd):
        cls = c.create_unicode_buffer(128)
        u.GetClassNameW(hwnd, cls, 128)
        if cls.value == 'Nemoterm':
            matches.append(hwnd)
    return True
u.EnumWindows(visit, 0)
if len(matches) != 1:
    raise RuntimeError(f'Expected one visible test window: {matches}')
hwnd = matches[0]
rect = w.RECT()
u.GetWindowRect(hwnd, c.byref(rect))
width, height = rect.right-rect.left, rect.bottom-rect.top
dc = u.GetWindowDC(hwnd)
mem = g.CreateCompatibleDC(dc)
bmp = g.CreateCompatibleBitmap(dc, width, height)
old = g.SelectObject(mem, bmp)
try:
    if not u.PrintWindow(hwnd, mem, 2):
        raise RuntimeError('PrintWindow failed')
    g.SelectObject(mem, old)
    header = struct.pack('<IiiHHIIiiII', 40, width, -height, 1, 32, 0, width*height*4, 0, 0, 0, 0)
    info = c.create_string_buffer(header)
    buf = c.create_string_buffer(width*height*4)
    if g.GetDIBits(mem, bmp, 0, height, buf, info, 0) != height:
        raise RuntimeError('GetDIBits failed')
    pixels = buf.raw
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            b, green, r, _a = pixels[(y*width+x)*4:(y*width+x+1)*4]
            raw.extend((r, green, b))
    def chunk(kind, data):
        return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data))
    png = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB', width,height,8,2,0,0,0))+chunk(b'IDAT', zlib.compress(raw))+chunk(b'IEND', b'')
    Path(sys.argv[2]).write_bytes(png)
    print(json.dumps({'pid':pid,'width':width,'height':height,'output':sys.argv[2]}))
finally:
    g.SelectObject(mem, old)
    g.DeleteObject(bmp)
    g.DeleteDC(mem)
    u.ReleaseDC(hwnd, dc)
