"""ConPTY child for native mouse integration tests; records actual VT input."""
import ctypes as c
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import sys
import threading
import time

report, control = map(Path, sys.argv[1:3])
k = c.windll.kernel32
k.GetStdHandle.argtypes = [w.DWORD]
k.GetStdHandle.restype = w.HANDLE
k.GetConsoleMode.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
k.SetConsoleMode.argtypes = [w.HANDLE, w.DWORD]
k.ReadFile.argtypes = [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p]
stdin = k.GetStdHandle(-10)
old = w.DWORD()
if not k.GetConsoleMode(stdin, c.byref(old)) or not k.SetConsoleMode(stdin, 0x280):
    raise c.WinError()
data = bytearray()
def reader():
    buf, n = c.create_string_buffer(1024), w.DWORD()
    while k.ReadFile(stdin, buf, len(buf), c.byref(n), None) and n.value:
        data.extend(buf.raw[:n.value])
threading.Thread(target=reader, daemon=True).start()
sys.stdout.reconfigure(encoding='utf-8')
phase = None
deadline = time.monotonic() + 60
print('\x1b]2;Nemoterm mouse integration test\x07', end='', flush=True)
try:
    while time.monotonic() < deadline:
        request = json.loads(control.read_text()) if control.exists() else {}
        if request.get('stop'):
            break
        if request.get('phase') != phase:
            phase = request.get('phase')
            data.clear()
            print('\x1b[?9;1000;1002;1003;1004;1005;1006;1015;1016l', end='')
            print(request.get('sequence', ''), end='', flush=True)
        size = os.get_terminal_size()
        snapshot = {'phase': phase, 'hex': data.hex(), 'columns': size.columns,
                    'rows': size.lines, 'input_mode': 0x280}
        temporary = report.with_suffix('.tmp')
        temporary.write_text(json.dumps(snapshot))
        os.replace(temporary, report)
        time.sleep(0.04)
finally:
    k.SetConsoleMode(stdin, old.value)
