"""DECSTR and saved private modes through the real HWND/ConPTY path."""
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, threading, time, read_snapshot, write_snapshot,
    wait_snapshot, memory_sample, wait_for, find_window, capture, scene)
from clipboard_test_utils import SavedClipboard, clipboard_text
import re

MARKER = b'\x1bP0$r\x1b\\'
with tempfile.TemporaryDirectory(prefix='nemoterm-state-') as directory:
    directory = Path(directory)
    report, control = directory/'report.json', directory/'control.json'
    process = subprocess.Popen([str(root/'dist/nemoterm.exe'), '--cols', '80', '--rows', '24',
        '-e', sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control)],
        env=dict(os.environ, NEMOTERM_CONPTY='bundled'), creationflags=subprocess.CREATE_NO_WINDOW)
    handle = k.OpenProcess(0x410, False, process.pid)
    samples, stop, evidence = [], threading.Event(), {}
    saved_clipboard = None
    def sampler():
        while not stop.is_set():
            samples.append(memory_sample(handle))
            stop.wait(.025)
    worker = threading.Thread(target=sampler, daemon=True)
    worker.start()
    def current():
        value = wait_snapshot(lambda: read_snapshot(report))
        assert not value.get('error') and process.poll() is None, value
        return value
    def received(predicate):
        def probe():
            value = current()
            return value if predicate(value) else None
        return wait_for(probe)
    def phase(name, sequence, expected=b''):
        write_snapshot(control, {'phase':name, 'preserve_mouse':True,
            'sequence':sequence+'\x1bP$qstate-marker\x1b\\'})
        try:
            value = received(lambda v: v.get('phase') == name and
                bytes.fromhex(v['hex']).endswith(expected+MARKER))
        except AssertionError:
            raise AssertionError((name, expected.hex(), current()))
        evidence[name] = {'reply':value['hex']}
        time.sleep(.08)
        return capture(hwnd, return_pixels=True)
    def key(vk):
        flags = 1 | (u.MapVirtualKeyW(vk, 0)<<16) | (1<<24)
        u.SendMessageW(hwnd, 0x100, vk, flags)
        u.SendMessageW(hwnd, 0x101, vk, flags | 0xc0000000)
    def mouse(message, flags=0, x=22, y=20):
        u.SendMessageW(hwnd, message, flags, (x&65535)|((y&65535)<<16))
    def input_bytes():
        time.sleep(.15)
        value = bytes.fromhex(current()['hex'])
        assert value.startswith(MARKER), value
        return value[len(MARKER):]
    try:
        hwnd = wait_for(lambda: find_window(process.pid))
        current()
        saved_clipboard = SavedClipboard(hwnd)
        baseline = phase('scene', scene('STATE CONTROL: KEEP TEXT AND SIXEL', '100;0;0') +
            '\x1b[?1002;1006;2004h\x1b[1;1H')
        reset = phase('soft-keeps-scene', '\x1b[?1;66h\x1b[4h\x1b[31;44;3;9m'
            '\x1b[!p\x1b[?25l\x1bP$qm\x1b\\\x1bP$qr\x1b\\',
            b'\x1bP1$r0m\x1b\\\x1bP1$r1;24r\x1b\\')
        assert reset == baseline, 'DECSTR changed existing text or Sixel pixels'
        evidence['soft-keeps-scene']['pixel_sha256'] = hashlib.sha256(reset).hexdigest()
        phase('soft-keyboard', '')
        key(0x26)
        assert input_bytes() == b'\x1b[A', current()
        phase('soft-mouse', '')
        mouse(0x201, 1); mouse(0x202)
        assert re.fullmatch(rb'\x1b\[<0;(\d+);(\d+)M\x1b\[<0;\1;\2m', input_bytes()), current()
        phase('saved-pixel-mouse', '\x1b[?1003;1016h\x1b[?1000;1005s'
            '\x1b[?1000;1006h\x1b[?1002;1015r\x1b[?1003$p\x1b[?1016$p',
            b'\x1b[?1003;1$y\x1b[?1016;1$y')
        phase('saved-pixel-motion', '')
        mouse(0x200, x=23); mouse(0x200, x=24)
        data = input_bytes()
        matches = re.findall(rb'\x1b\[<35;(\d+);(\d+)M', data)
        assert len(matches) >= 2 and int(matches[-1][0]) == int(matches[-2][0])+1, data
        evidence['saved-pixel-motion']['input'] = data.hex()
        old_size = current()
        assert u.MoveWindow(hwnd, 40, 40, 640, 480, True)
        dimensions = received(lambda v: v['columns'] != old_size['columns'])
        phase('saved-after-resize', '\x1b[?1000;1006h\x1b[?1000;1005r'
            '\x1b[?1003$p\x1b[?1016$p', b'\x1b[?1003;1$y\x1b[?1016;1$y')
        evidence['saved-after-resize']['dimensions'] = [dimensions['columns'], dimensions['rows']]
        phase('saved-resized-motion', '')
        mouse(0x200, x=43); mouse(0x200, x=44)
        data = input_bytes()
        matches = re.findall(rb'\x1b\[<35;(\d+);(\d+)M', data)
        # Resizing can centre the grid within the client area's remainder.
        # One client pixel must still advance exactly one reported pixel.
        assert len(matches) == 2 and int(matches[1][0]) == int(matches[0][0])+1, data
        assert matches[0][1] == matches[1][1], data
        evidence['saved-resized-motion']['input'] = data.hex()
        phase('shift-selection', '\x1b[1;1H\x1b[2KSELECTABLE')
        rect = w.RECT(); u.GetClientRect(hwnd, c.byref(rect))
        cell = (rect.right-2)//dimensions['columns']
        mouse(0x201, 5, 3, 6); mouse(0x200, 5, 3+9*cell, 6)
        mouse(0x202, 4, 3+9*cell, 6)
        mouse(0x204, 4, 3, 6); mouse(0x205, 4, 3, 6)
        wait_for(lambda: clipboard_text(hwnd) == 'SELECTABLE')
        assert input_bytes() == b'', current()
        evidence['shift-selection']['copied'] = clipboard_text(hwnd)
        mouse(0x201, 5, 3, 6); mouse(0x202, 4, 3, 6)
        # Frame atomicity survives soft reset; no input is injected while frozen.
        before = phase('before-freeze', '\x1b[?1003l\x1b[?25l')
        frozen = phase('soft-frozen', '\x1b[?2026h\x1b[10;1HAFTER SOFT RESET'
            '\x1b[!p\x1b[?25l\x1b[?2026$p', b'\x1b[?2026;1$y')
        assert frozen == before, 'soft reset released a synchronized frame'
        phase('soft-released', '\x1b[?2026l')
        wait_for(lambda: capture(hwnd, return_pixels=True) != before, timeout=.8)
        capture(hwnd, 'state-control-window.png')
        # DEC origin changes home the cursor and CPR uses origin-relative rows.
        phase('origin-and-saved-cursor', '\x1b[3;10r\x1b[?6h\x1b[6n'
            '\x1b[4;8H\x1b7\x1b[?6l\x1b8\x1b[6n', b'\x1b[1;1R\x1b[4;8R')
        phase('alt-soft-reset', '\x1b[r\x1b[?6l\x1b[5;6H\x1b[?1049h'
            '\x1b[9;10H\x1b7\x1b[!p\x1b[6n\x1b8\x1b[6n'
            '\x1b[?1049l\x1b[6n', b'\x1b[9;10R\x1b[1;1R\x1b[5;6R')
        evidence.update(peak_private_ws=max(s['private_ws'] for s in samples),
            peak_total_ws=max(s['total_ws'] for s in samples),
            peak_private_commit=max(s['private_commit'] for s in samples),
            executable_sha256=hashlib.sha256((root/'dist/nemoterm.exe').read_bytes()).hexdigest())
        assert evidence['peak_private_ws'] < 20_000_000, evidence
        assert evidence['peak_total_ws'] < 50_000_000, evidence
        print('Native state control passed:', json.dumps(evidence))
    finally:
        evidence['last_snapshot'] = read_snapshot(report)
        (root/'research/state-control-observed.json').write_text(json.dumps(evidence, indent=2))
        if saved_clipboard: saved_clipboard.restore()
        stop.set(); worker.join(2); k.CloseHandle(handle)
        write_snapshot(control, {'stop':True})
        process.wait(timeout=10)
