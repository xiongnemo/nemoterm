"""ConPTY child for native mouse integration tests; records actual VT input."""
import ctypes as c
import codecs
import hashlib
from ctypes import wintypes as w
import os
from pathlib import Path
import sys
import threading
import time
import traceback
from fixture_io import load_sequence, read_snapshot, write_snapshot

report, control = map(Path, sys.argv[1:3])
# Settings lifecycle tests need time for several modal UI Automation rounds.
# Keep the ordinary fixture's one-minute bound. Dense local 160x48 image
# workloads can explicitly opt into a longer, still bounded child lifetime.
lifetime = int(sys.argv[3]) if len(sys.argv) > 3 else 60
assert 1 <= lifetime <= 1800
k = c.windll.kernel32
k.GetStdHandle.argtypes = [w.DWORD]
k.GetStdHandle.restype = w.HANDLE
k.GetConsoleMode.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
k.SetConsoleMode.argtypes = [w.HANDLE, w.DWORD]
k.ReadFile.argtypes = [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p]
k.WriteFile.argtypes = [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p]
k.ReadConsoleW.argtypes = [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p]

class Coord(c.Structure):
    _fields_ = [('x', w.SHORT), ('y', w.SHORT)]

class SmallRect(c.Structure):
    _fields_ = [(name, w.SHORT) for name in ('left', 'top', 'right', 'bottom')]

class ScreenInfo(c.Structure):
    _fields_ = [('size', Coord), ('cursor', Coord), ('attributes', w.WORD),
               ('window', SmallRect), ('maximum', Coord)]

class NativeCell(c.Structure):
    _fields_ = [('unit', w.WORD), ('attributes', w.WORD)]

k.ReadConsoleOutputW.argtypes = [w.HANDLE, c.POINTER(NativeCell), Coord, Coord, c.POINTER(SmallRect)]
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
# Only the hosted resize fixture requests per-read geometry. Keep its original
# chunks (including split CSI sequences) across phases; do not sample other tests.
resize_reads = [] if os.environ.get('NEMOTERM_TEST_RESIZE_READS') == '1' else None
def reader():
    if wide_input:
        buf, n = c.create_string_buffer(2048), w.DWORD()
        decoder = codecs.getincrementaldecoder('utf-16-le')()
        while k.ReadConsoleW(stdin, buf, 1024, c.byref(n), None) and n.value:
            data.extend(decoder.decode(buf.raw[:n.value*2]).encode('utf-8'))
        return
    buf, n = c.create_string_buffer(1024), w.DWORD()
    while k.ReadFile(stdin, buf, len(buf), c.byref(n), None) and n.value:
        chunk = buf.raw[:n.value]
        if resize_reads is not None and len(resize_reads) < 512:
            info = ScreenInfo()
            ok = k.GetConsoleScreenBufferInfo(stdout, c.byref(info))
            grid = [info.window.right - info.window.left + 1,
                    info.window.bottom - info.window.top + 1] if ok else None
            resize_reads.append(dict(wire=chunk.hex(), grid=grid))
        data.extend(chunk)
threading.Thread(target=reader, daemon=True).start()
sys.stdout.reconfigure(encoding='utf-8',
    newline='' if exact_output else None)
phase = None
output_write = None
applied_blob = None
request = {}
responded = set()
barrier_sent = barrier_ack = None
barrier_start = 0
stop_record = None
deadline = time.monotonic() + lifetime
print('\x1b]2;Nemoterm mouse integration test\x07', end='', flush=True)
try:
    while time.monotonic() < deadline:
        request = read_snapshot(control) or request
        if request.get('stop'):
            if request.get('observe_exit'):
                stop_record = dict(pid=os.getpid(), phase='stop-seen', seen_ns=time.perf_counter_ns())
                write_snapshot(report.parent/'stop.json', stop_record)
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
            sequence = load_sequence(control, request)
            output_write = None
            if style := request.get('output_write'):
                assert exact_output and request.get('preserve_mouse') and style in ('whole','bytewise')
                barrier_sent = request['input_barrier']
                barrier_start = 0
                wire = (sequence+'\x1b[5n').encode('ascii')
                chunk = 1 if style=='bytewise' else len(wire)
                calls = 0
                for offset in range(0,len(wire),chunk):
                    part=wire[offset:offset+chunk]; written=w.DWORD()
                    if not k.WriteFile(stdout,part,len(part),c.byref(written),None):raise c.WinError()
                    assert written.value==len(part); calls+=1
                output_write=dict(style=style,api='WriteFile(console stdout)',calls=calls,
                    bytes=len(wire),max_chunk=chunk,sha256=hashlib.sha256(wire).hexdigest())
            else:
                print(sequence, end='', flush=True)
            applied_blob = request.get('sequence_blob')
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
        if resize_reads is not None: snapshot['resize_reads'] = resize_reads.copy()
        if output_write: snapshot['output_write']=output_write
        if request.get('report_responses'):
            snapshot['flushed_responses'] = sorted(responded)
        if applied_blob is not None:
            snapshot['applied_blob'] = applied_blob
        if request.get('report_cursor') or request.get('native_row'):
            info=ScreenInfo()
            if not k.GetConsoleScreenBufferInfo(stdout, c.byref(info)):
                raise c.WinError()
            snapshot['screen_cursor']=[info.cursor.x-info.window.left,
                                       info.cursor.y-info.window.top]
            if request.get('native_row'):
                x, y, length = request['native_row']
                assert 0 <= x and 0 <= y and 0 < length <= 80
                left, top = info.window.left + x, info.window.top + y
                rect = SmallRect(left, top, left + length - 1, top)
                buf = (NativeCell * length)()
                if not k.ReadConsoleOutputW(stdout, buf, Coord(length, 1), Coord(0, 0), c.byref(rect)):
                    raise c.WinError()
                assert (rect.left, rect.top, rect.right, rect.bottom) == (left, top, left + length - 1, top)
                snapshot['native_row'] = [[cell.unit, cell.attributes] for cell in buf]
        if barrier is not None:
            snapshot['input_barrier'] = barrier_ack
        write_snapshot(report, snapshot)
        time.sleep(0.04)
except Exception:
    write_snapshot(report, {'error': traceback.format_exc(), 'phase': phase})
    raise
finally:
    input_restored = bool(k.SetConsoleMode(stdin, old.value))
    cp_restored = bool(k.SetConsoleCP(old_input_cp))
    output_restored = not exact_output or bool(k.SetConsoleMode(stdout, old_output.value))
    if stop_record is not None:
        restored = dict(input_mode=input_restored, input_cp=cp_restored, output_mode=output_restored)
        stop_record.update(phase='console-restored' if all(restored.values()) else 'restore-failed',
                           restored=restored, restored_ns=time.perf_counter_ns())
        write_snapshot(report.parent/'stop.json', stop_record)
