"""Verify cursor pixels, status queries and keyboard capabilities through ConPTY."""
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, threading, time, read_snapshot, write_snapshot,
    memory_sample, wait_for, find_window, capture)

u.GetClientRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.GetForegroundWindow.restype = w.HWND
u.GetCaretBlinkTime.restype = w.UINT

with tempfile.TemporaryDirectory(prefix='nemoterm-query-') as directory:
    directory = Path(directory)
    report, control = directory/'report.json', directory/'control.json'
    process = subprocess.Popen([str(root/'dist/nemoterm.exe'), '--cols', '40', '--rows', '12',
        '-e', sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control)],
        env=dict(os.environ, NEMOTERM_CONPTY='bundled'), creationflags=subprocess.CREATE_NO_WINDOW)
    handle = k.OpenProcess(0x410, False, process.pid)
    samples, stop = [], threading.Event()
    evidence = {}
    def sampler():
        while not stop.is_set():
            samples.append(memory_sample(handle))
            stop.wait(0.025)
    worker = threading.Thread(target=sampler, daemon=True)
    worker.start()
    def current():
        value = read_snapshot(report)
        assert not value.get('error') and process.poll() is None, value
        return value
    def phase(name, sequence, expected):
        write_snapshot(control, {'phase':name, 'sequence':sequence})
        try:
            wait_for(lambda: current().get('phase') == name and
                     expected in bytes.fromhex(current().get('hex', '')))
        except AssertionError:
            raise AssertionError((name, expected, current()))
        time.sleep(0.08)
        pixels = capture(hwnd, return_pixels=True)
        evidence[name] = dict(reply=current()['hex'], sha256=hashlib.sha256(pixels).hexdigest())
        return pixels
    def cursor_shape(pixels):
        rect = w.RECT()
        u.GetClientRect(hwnd, c.byref(rect))
        indices = [i//3 for i in range(0, len(pixels), 3) if pixels[i:i+3] == b'\xff\0\0']
        if not indices: return [0, 0, 0]
        xs, ys = [i%rect.right for i in indices], [i//rect.right for i in indices]
        return [max(xs)-min(xs)+1, max(ys)-min(ys)+1, len(indices)]
    try:
        hwnd = wait_for(lambda: find_window(process.pid))
        wait_for(current)
        blank = phase('hidden', '\x1b[0m\x1b[2 q\x1b[?25l\x1b[2J\x1b[2;2H'
            '\x1b]10;rgb:f/f/f\x07\x1b]11;rgb:0/0/0\x07\x1b]12;rgb:f/0/0\x07'
            '\x1bP$q q\x1b\\', b'\x1bP1$r2 q\x1b\\')
        shapes = []
        for style, name in [(2, 'block'), (4, 'underline'), (6, 'bar')]:
            pixels = phase(name, f'\x1b[?25h\x1b[{style} q\x1bP$q q\x1b\\',
                           f'\x1bP1$r{style} q\x1b\\'.encode())
            shape = cursor_shape(pixels)
            shapes.append(shape)
            evidence[name]['shape'] = shape
            capture(hwnd, 'cursor-'+name+'.png')
        assert shapes[0][0] > 1 and shapes[0][1] > 1, shapes
        assert shapes[1][0] > 1 and shapes[1][1] == 1, shapes
        assert shapes[2][0] == 1 and shapes[2][1] > 1, shapes
        hidden = phase('hidden-again', '\x1b[?25l\x1bP$q q\x1b\\', b'\x1bP1$r6 q\x1b\\')
        assert hidden == blank, 'cursor left stale pixels when hidden'
        phase('sgr', '\x1b[31;44m\x1bP$qm\x1b\\', b'\x1bP1$r0;31;44m\x1b\\')
        phase('margins', '\x1b[3;10r\x1bP$qr\x1b\\', b'\x1bP1$r3;10r\x1b\\')
        phase('unsupported', '\x1bP$qfuture-query\x1b\\', b'\x1bP0$r\x1b\\')
        phase('geometry', '\x1bP$q$|\x1b\\\x1bP$q*|\x1b\\',
              b'\x1bP1$r40$|\x1b\\\x1bP1$r12*|\x1b\\')
        assert u.MoveWindow(hwnd, 30, 30, 650, 470, True)
        wait_for(lambda: current().get('columns', 40) != 40)
        dimensions = current()
        expected = f"\x1bP1$r{dimensions['columns']}$|\x1b\\\x1bP1$r{dimensions['rows']}*|\x1b\\"
        phase('geometry-after-resize', '\x1bP$q$|\x1b\\\x1bP$q*|\x1b\\', expected.encode())

        phase('blink', '\x1b[0m\x1b[r\x1b[2J\x1b[2;2H\x1b[?25h\x1b[1 q\x1bP$q q\x1b\\',
              b'\x1bP1$r1 q\x1b\\')
        blink_ms = u.GetCaretBlinkTime()
        if u.GetForegroundWindow() == hwnd and 0 < blink_ms <= 1000:
            states = set()
            deadline = time.monotonic()+2.5*blink_ms/1000
            while time.monotonic() < deadline:
                states.add(cursor_shape(capture(hwnd, return_pixels=True))[2] > 0)
                time.sleep(0.06)
            evidence['blink_states'] = sorted(states)
            assert states == {False, True}, evidence
        else:
            evidence['blink_pixel_check_skipped'] = 'No foreground focus or system blink disabled/slow'
        steady = phase('blink-off', '\x1b[?12l\x1b[?12$p\x1bP$q q\x1b\\',
              b'\x1b[?12;2$y\x1bP1$r2 q\x1b\\')
        if u.GetForegroundWindow() == hwnd and 0 < blink_ms <= 1000:
            states = set()
            deadline = time.monotonic()+2.5*blink_ms/1000
            while time.monotonic() < deadline:
                states.add(cursor_shape(capture(hwnd, return_pixels=True))[2] > 0)
                time.sleep(0.06)
            evidence['steady_states'] = sorted(states)
            assert states == {True}, evidence
        frozen = phase('frozen-query', '\x1b[?2026h\x1b[6 q\x1bP$q q\x1b\\',
                       b'\x1bP1$r6 q\x1b\\')
        assert frozen == steady, 'cursor change escaped synchronized presentation'
        released = phase('released-query', '\x1b[?2026l\x1bP$q q\x1b\\',
                         b'\x1bP1$r6 q\x1b\\')
        assert cursor_shape(released)[:2] == shapes[2][:2]
        # Inject messages only into our own HWND. This exercises the real
        # Win32 translator; modifier combinations are tested by test_tcap.
        # Query values must match both the protocol oracle and the child input.
        keys = [('kf1', 0x70, b'\x1bOP', False), ('kf12', 0x7b, b'\x1b[24~', False),
                ('kf13', 0x7c, b'\x1b[25~', False), ('kf24', 0x87, b'\x1b[45~', False),
                ('khome', 0x24, b'\x1b[H', True), ('kend', 0x23, b'\x1b[F', True),
                ('kcuu1', 0x26, b'\x1b[A', True), ('kcud1', 0x28, b'\x1b[B', True),
                ('kcuf1', 0x27, b'\x1b[C', True), ('kcub1', 0x25, b'\x1b[D', True),
                ('kich1', 0x2d, b'\x1b[2~', True), ('kdch1', 0x2e, b'\x1b[3~', True),
                ('kpp', 0x21, b'\x1b[5~', True), ('knp', 0x22, b'\x1b[6~', True),
                ('kbs', 0x08, b'\x7f', False)]
        encoded_names = ';'.join(name.encode().hex() for name, *_ in keys)
        for app in (False, True):
            values = [value.replace(b'\x1b[', b'\x1bO')
                      if app and name in ('khome', 'kend', 'kcuu1', 'kcud1', 'kcuf1', 'kcub1')
                      else value for name, _, value, _ in keys]
            expected = b'\x1bP1+r'+b';'.join(name.encode().hex().encode()+b'='+value.hex().encode()
                for (name, *_), value in zip(keys, values))+b'\x1b\\'
            name = 'keys-application' if app else 'keys-normal'
            phase(name, f'\x1b[?1{"h" if app else "l"}\x1bP+q{encoded_names}\x1b\\', expected)
            for _, vk, _, extended in keys:
                flags = 1 | (u.MapVirtualKeyW(vk, 0) << 16) | (int(extended) << 24)
                u.SendMessageW(hwnd, 0x100, vk, flags)
                u.SendMessageW(hwnd, 0x101, vk, flags | 0xc0000000)
            expected_input = expected+b''.join(values)
            try:
                wait_for(lambda: bytes.fromhex(current().get('hex', '')) == expected_input)
            except AssertionError:
                raise AssertionError((name, expected_input.hex(), current()))
            evidence[name].update(key_input=b''.join(values).hex(), child_input=current()['hex'])
        phase('tcap-colours', '\x1bP+q436f;544e;524742\x1b\\',
              b'\x1bP1+r436f=323536;544e=787465726d2d323536636f6c6f72;524742=38\x1b\\')
        phase('tcap-unsupported', '\x1bP+q637570\x1b\\', b'\x1bP0+r\x1b\\')
        evidence.update(peak_private_ws=max(s['private_ws'] for s in samples),
                        peak_total_ws=max(s['total_ws'] for s in samples),
                        executable_sha256=hashlib.sha256((root/'dist/nemoterm.exe').read_bytes()).hexdigest())
        assert evidence['peak_private_ws'] < 20_000_000, evidence
        (root/'research/query-window-observed.json').write_text(json.dumps(evidence, indent=2))
        print('Native cursor pixels, queries and keyboard capabilities passed:', evidence)
    finally:
        stop.set()
        worker.join(2)
        k.CloseHandle(handle)
        write_snapshot(control, {'stop': True})
        process.wait(timeout=10)
