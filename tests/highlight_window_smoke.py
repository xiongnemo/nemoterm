"""1001 handshake, highlight pixels and cleanup through an own HWND/ConPTY."""
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, threading, time, read_snapshot, write_snapshot,
    memory_sample, wait_for, find_window, capture)

u.GetClientRect.argtypes = [w.HWND, c.POINTER(w.RECT)]

with tempfile.TemporaryDirectory(prefix='nemoterm-highlight-') as directory:
    directory = Path(directory)
    report, control = directory/'report.json', directory/'control.json'
    process = subprocess.Popen([str(root/'dist/nemoterm.exe'), '--cols', '40', '--rows', '12',
        '-e', sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control)],
        env=dict(os.environ, NEMOTERM_CONPTY='bundled'), creationflags=subprocess.CREATE_NO_WINDOW)
    handle = k.OpenProcess(0x410, False, process.pid)
    samples, stop, evidence = [], threading.Event(), {}
    def sample():
        while not stop.is_set():
            samples.append(memory_sample(handle))
            stop.wait(0.025)
    worker = threading.Thread(target=sample, daemon=True)
    worker.start()
    def current():
        value = read_snapshot(report)
        assert not value.get('error') and process.poll() is None, value
        return value
    def observed(predicate):
        def probe():
            value = current()
            return value if predicate(value) else None
        return wait_for(probe)
    def has(data):
        return observed(lambda value: data in bytes.fromhex(value.get('hex', '')))
    def msg(kind, col, row, wp=0):
        x, y = 1+col*cw+cw//2, 1+row*ch+ch//2
        return u.SendMessageW(hwnd, kind, wp, (x & 0xffff) | ((y & 0xffff) << 16))
    def phase(name, handshake=True):
        # A normal-tracking click resets the frontend multi-click chain. It
        # targets only our HWND and is discarded with the setup phase's log.
        write_snapshot(control, {'phase':name+'-reset', 'sequence':'\x1b[?1000;1006h\x1b[?1000$p'})
        observed(lambda value: value.get('phase') == name+'-reset' and
                 b'\x1b[?1000;1$y' in bytes.fromhex(value.get('hex', '')))
        msg(0x201, 2, 3, 1); msg(0x202, 2, 3)
        has(b'\x1b[<0;3;4m')
        reply = '\x1b[1;3;4;2;8T' if handshake else ''
        seq = '\x1b[0m\x1b[?25l\x1b[2J\x1b]10;rgb:f/f/f\x07\x1b]11;rgb:0/0/0\x07'
        seq += ''.join(f'\x1b[{row};1Hone two three '+26*'x' for row in range(1, 13))
        seq += '\x1b[1;1H\x1b[?1001;1006h\x1b[?1001$p'
        write_snapshot(control, {'phase':name, 'sequence':seq, 'responses':{
            'press':{'trigger':b'\x1b[<0;3;4M'.hex(), 'sequence':reply+'\x1b[?1000$p'}}})
        observed(lambda value: value.get('phase') == name and
                 b'\x1b[?1001;1$y' in bytes.fromhex(value.get('hex', '')))
        time.sleep(0.08)
        baseline = capture(hwnd, return_pixels=True)
        msg(0x201, 2, 3, 1)
        has(b'\x1b[?1000;2$y')
        return baseline
    def select(baseline):
        msg(0x200, 8, 3, 1)
        return wait_for(lambda: (pixels := capture(hwnd, return_pixels=True)) != baseline and pixels)
    try:
        hwnd = wait_for(lambda: find_window(process.pid))
        observed(lambda value: 'columns' in value)
        rect = w.RECT(); u.GetClientRect(hwnd, c.byref(rect))
        cw, ch = (rect.right-2)//40, (rect.bottom-2)//12
        baseline = phase('forward')
        selected = select(baseline)
        capture(hwnd, 'highlight-selection.png')
        evidence['highlight_pixel_change'] = sum(a != b for a, b in zip(selected, baseline))
        changed = [i//3 for i in range(0, len(selected), 3)
                   if selected[i:i+3] != baseline[i:i+3]]
        xs, ys = [i%rect.right for i in changed], [i//rect.right for i in changed]
        bounds = [min(xs), min(ys), max(xs)+1, max(ys)+1]
        evidence['highlight_bounds'] = bounds
        assert bounds[2]-bounds[0] == 6*cw and bounds[3]-bounds[1] == ch, bounds
        msg(0x202, 8, 3)
        evidence['forward'] = has(b'\x1b[<9;4t')['hex']
        wait_for(lambda: capture(hwnd, return_pixels=True) == baseline)
        baseline = phase('reverse')
        msg(0x200, 0, 3, 1); msg(0x202, 0, 3)
        evidence['reverse'] = has(b'\x1b[<1;4;3;4;1;4T')['hex']
        wait_for(lambda: capture(hwnd, return_pixels=True) == baseline)
        baseline = phase('multi-click')
        msg(0x202, 2, 3)  # empty character selection
        msg(0x201, 5, 3, 1)
        wait_for(lambda: capture(hwnd, return_pixels=True) != baseline)
        msg(0x202, 5, 3)
        has(b'\x1b[<5;4;8;4;6;4T')
        msg(0x201, 5, 3, 1); msg(0x202, 5, 3)
        evidence['multi-click'] = has(b'\x1b[<1;4;41;4;6;4T')['hex']
        wait_for(lambda: capture(hwnd, return_pixels=True) == baseline)
        baseline = phase('capture-cancel')
        select(baseline)
        u.SendMessageW(hwnd, 0x1f, 0, 0)  # WM_CANCELMODE
        evidence['capture-cancel'] = has(b'\x1b[<9;4t')['hex']
        wait_for(lambda: capture(hwnd, return_pixels=True) == baseline)
        baseline = phase('shift-takeover')
        select(baseline)
        msg(0x200, 9, 3, 5)  # MK_LBUTTON | MK_SHIFT
        completion = has(b'\x1b[<9;4t')['hex']
        msg(0x200, 12, 3, 5); msg(0x202, 12, 3, 4)
        time.sleep(0.1)
        assert observed(lambda value: 'hex' in value)['hex'] == completion
        assert capture(hwnd, return_pixels=True) != baseline, 'Shift selection did not persist'
        evidence['shift-takeover'] = completion
        baseline = phase('timeout', handshake=False)
        u.SendMessageW(hwnd, 0x100, 0x70, 1)  # F1 while awaiting the host
        u.SendMessageW(hwnd, 0x101, 0x70, 0xc0000001)
        has(b'\x1bOP')
        evidence['timeout'] = has(b'\x1b[<0;3;4m')['hex']
        msg(0x202, 2, 3)
        assert capture(hwnd, return_pixels=True) == baseline
        baseline = phase('resize')
        select(baseline)
        assert u.MoveWindow(hwnd, 30, 30, 650, 470, True)
        evidence['resize'] = has(b'\x1b[<9;4t')['hex']
        dimensions = observed(lambda value: value.get('columns', 40) != 40)
        evidence['resized_grid'] = [dimensions['columns'], dimensions['rows']]
        msg(0x202, 8, 3)
        evidence.update(peak_private_ws=max(s['private_ws'] for s in samples),
                        peak_total_ws=max(s['total_ws'] for s in samples),
                        executable_sha256=hashlib.sha256((root/'dist/nemoterm.exe').read_bytes()).hexdigest())
        assert evidence['peak_private_ws'] < 20_000_000, evidence
        (root/'research/highlight-window-observed.json').write_text(json.dumps(evidence, indent=2))
        print('Native highlight pixels, handshake, input and cleanup passed:', evidence)
    finally:
        stop.set(); worker.join(2); k.CloseHandle(handle)
        write_snapshot(control, {'stop':True})
        process.wait(timeout=10)
