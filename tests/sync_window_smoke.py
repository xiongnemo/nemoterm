"""Pixel and working-set checks on a newly spawned Nemoterm/ConPTY window."""
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess, sys,
    tempfile, Path, threading, time, read_snapshot, write_snapshot, memory_sample,
    wait_for, find_window, capture, scene, wait_snapshot)

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
        return wait_snapshot(current, lambda value: value.get('phase') == name and
                        reply in bytes.fromhex(value.get('hex', '')))
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
