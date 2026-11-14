"""ConPTY child for native mouse integration tests; records actual VT input."""
import ctypes as c
import codecs
from ctypes import wintypes as w
import os
from pathlib import Path
import sys
import threading
import time
import traceback
from fixture_io import read_snapshot, write_snapshot

report, control = map(Path, sys.argv[1:3])
# Settings lifecycle tests need time for several modal UI Automation rounds.
# Keep the ordinary fixture's one-minute bound; opt in explicitly up to five.
lifetime = int(sys.argv[3]) if len(sys.argv) > 3 else 60
assert 1 <= lifetime <= 300
k = c.windll.kernel32
k.GetStdHandle.argtypes = [w.DWORD]
k.GetStdHandle.restype = w.HANDLE
k.GetConsoleMode.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
k.SetConsoleMode.argtypes = [w.HANDLE, w.DWORD]
k.ReadFile.argtypes = [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p]
k.ReadConsoleW.argtypes = [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p]

class Coord(c.Structure):
    _fields_ = [('x', w.SHORT), ('y', w.SHORT)]

class SmallRect(c.Structure):
    _fields_ = [(name, w.SHORT) for name in ('left', 'top', 'right', 'bottom')]

class ScreenInfo(c.Structure):
    _fields_ = [('size', Coord), ('cursor', Coord), ('attributes', w.WORD),
               ('window', SmallRect), ('maximum', Coord)]

k.GetConsoleScreenBufferInfo.argtypes = [w.HANDLE, c.POINTER(ScreenInfo)]
stdin = k.GetStdHandle(-10)
stdout = k.GetStdHandle(-11)
old_output = w.DWORD()
exact_output = os.environ.get('NEMOTERM_TEST_EXACT_OUTPUT') == '1'
if exact_output:
    if not k.GetConsoleMode(stdout, c.byref(old_output)) or not k.SetConsoleMode(
            stdout, old_output.value | 0x4 | 0x8):
        raise c.WinError()
old_input_cp = k.GetConsoleCP()
if os.environ.get('NEMOTERM_TEST_INPUT_CP'):
    requested_cp = int(os.environ['NEMOTERM_TEST_INPUT_CP'])
    assert requested_cp in (65001, 28591)
    assert k.SetConsoleCP(requested_cp)
elif os.environ.get("NEMOTERM_TEST_UTF8_INPUT") == "1":
    assert k.SetConsoleCP(65001)
old = w.DWORD()
if not k.GetConsoleMode(stdin, c.byref(old)) or not k.SetConsoleMode(stdin, 0x280):
    raise c.WinError()
data = bytearray()
wide_input = os.environ.get('NEMOTERM_TEST_WIDE_INPUT') == '1'
def reader():
    if wide_input:
        buf, n = c.create_string_buffer(2048), w.DWORD()
        decoder = codecs.getincrementaldecoder('utf-16-le')()
        while k.ReadConsoleW(stdin, buf, 1024, c.byref(n), None) and n.value:
            data.extend(decoder.decode(buf.raw[:n.value*2]).encode('utf-8'))
        return
    buf, n = c.create_string_buffer(1024), w.DWORD()
    while k.ReadFile(stdin, buf, len(buf), c.byref(n), None) and n.value:
        data.extend(buf.raw[:n.value])
threading.Thread(target=reader, daemon=True).start()
sys.stdout.reconfigure(encoding='utf-8',
    newline='' if exact_output else None)
phase = None
request = {}
responded = set()
barrier_sent = barrier_ack = None
barrier_start = 0
deadline = time.monotonic() + lifetime
print('\x1b]2;Nemoterm mouse integration test\x07', end='', flush=True)
try:
    while time.monotonic() < deadline:
        request = read_snapshot(control) or request
        if request.get('stop'):
            break
        if request.get('phase') != phase:
            phase = request.get('phase')
            if os.environ.get('NEMOTERM_TEST_INPUT_CP'):
                assert k.SetConsoleCP(requested_cp)
            data.clear()
            responded.clear()
            barrier_sent = barrier_ack = None
            if not request.get('preserve_mouse'):
                print('\x1b[?9;1000;1001;1002;1003;1004;1005;1006;1015;1016l', end='')
            print(request.get('sequence', ''), end='', flush=True)
        # A cooperating application can answer a mouse report without
        # changing phases, clearing input, or resetting the tracking mode.
        for name, reply in request.get('responses', {}).items():
            if name not in responded and bytes.fromhex(reply['trigger']) in data:
                print(reply['sequence'], end='', flush=True)
                responded.add(name)
        # A DSR reply traverses the same ordered ConPTY input path as mouse
        # reports. Publish an acknowledgement only after all earlier input
        # has reached this child, without clearing the phase or its events.
        barrier = request.get('input_barrier')
        if barrier is not None and barrier != barrier_sent:
            barrier_start = len(data)
            barrier_sent = barrier
            print('\x1b[5n', end='', flush=True)
        if barrier_sent is not None and b'\x1b[0n' in data[barrier_start:]:
            barrier_ack = barrier_sent
        size = os.get_terminal_size()
        snapshot = {'phase': phase, 'hex': data.hex(), 'columns': size.columns,
                    'rows': size.lines, 'input_mode': 0x280, 'input_cp': k.GetConsoleCP(),
                    'input_api': 'ReadConsoleW' if wide_input else 'ReadFile'}
        if request.get('report_cursor'):
            info=ScreenInfo()
            if not k.GetConsoleScreenBufferInfo(stdout, c.byref(info)):
                raise c.WinError()
            snapshot['screen_cursor']=[info.cursor.x-info.window.left,
                                       info.cursor.y-info.window.top]
        if barrier is not None:
            snapshot['input_barrier'] = barrier_ack
        write_snapshot(report, snapshot)
        time.sleep(0.04)
except Exception:
    write_snapshot(report, {'error': traceback.format_exc(), 'phase': phase})
    raise
finally:
    k.SetConsoleMode(stdin, old.value)
    k.SetConsoleCP(old_input_cp)
    if exact_output:
        k.SetConsoleMode(stdout, old_output.value)
