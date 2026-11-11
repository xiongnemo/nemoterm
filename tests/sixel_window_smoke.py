"""Exact Sixel pixels across own-window resize, scroll margins and history."""
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, threading, time, read_snapshot, write_snapshot,
    memory_sample, wait_for, wait_snapshot, find_window, capture)

u.GetClientRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]

def solid(width, height):
    bands = ''.join(f'!{width}{chr(63+(1 << min(6, height-y))-1)}-'
                    for y in range(0, height, 6))
    return f'\x1bP0;1q"1;1;{width};{height}#1;2;100;0;0'+bands+'\x1b\\'

with tempfile.TemporaryDirectory(prefix='nemoterm-sixel-') as directory:
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
    def phase(name, sequence):
        write_snapshot(control, {'phase':name, 'sequence':sequence+'\x1b[?80$p'})
        return wait_snapshot(current, lambda v: v.get('phase') == name and
                             b'\x1b[?80;2$y' in bytes.fromhex(v.get('hex', '')))
    def resize(cols, rows):
        client, window = w.RECT(), w.RECT()
        u.GetClientRect(hwnd, c.byref(client)); u.GetWindowRect(hwnd, c.byref(window))
        fw = window.right-window.left-client.right
        fh = window.bottom-window.top-client.bottom
        assert u.MoveWindow(hwnd, 30, 30, cols*cw+2+fw, rows*ch+2+fh, True)
        wait_snapshot(current, lambda v: v.get('columns') == cols and v.get('rows') == rows)
    def check(name, rows, cols=40, screen_rows=12, erased=None):
        # Red pixels are the image only: blank black text grid, hidden cursor.
        expected = {(x, y) for row in rows if 0 <= row < screen_rows
                    for y in range(1+row*ch, 1+(row+1)*ch)
                    for x in range(1+20*cw, 1+min(26, cols)*cw)}
        if erased:
            for col, row in erased:
                expected.difference_update((x, y) for y in range(1+row*ch, 1+(row+1)*ch)
                                           for x in range(1+col*cw, 1+(col+1)*cw))
        last = set()
        def matches():
            nonlocal last
            rect = w.RECT(); u.GetClientRect(hwnd, c.byref(rect))
            pixels = capture(hwnd, return_pixels=True)
            last = {(i//3 % rect.right, i//3 // rect.right) for i in range(0, len(pixels), 3)
                    if pixels[i:i+3] == b'\xff\0\0'}
            return last == expected
        try:
            wait_for(matches)
        except AssertionError:
            capture(hwnd, 'sixel-failure.png')
            raise AssertionError((name, len(expected), len(last),
                                  sorted(expected-last)[:6], sorted(last-expected)[:6]))
        evidence[name] = {'red_pixels':len(expected), 'grid':[cols, screen_rows]}
    def draw(name):
        phase(name, '\x1b[?80l\x1b[r\x1b[?25l\x1b[0m\x1b[2J\x1b[3J'
              '\x1b]11;rgb:0/0/0\x07\x1b[2;21H'+solid(6*cw, 6*ch)+'\x1b[H')
        check(name, range(1, 7))
    try:
        hwnd = wait_for(lambda: find_window(process.pid))
        wait_snapshot(current, lambda v: v.get('columns') == 40 and v.get('rows') == 12)
        rect = w.RECT(); u.GetClientRect(hwnd, c.byref(rect))
        cw, ch = (rect.right-2)//40, (rect.bottom-2)//12
        draw('initial')
        resize(24, 12); check('width-clipped', range(1, 7), 24)
        resize(40, 12); check('width-restored', range(1, 7))
        phase('cursor-bottom', '\x1b[12;1H')
        resize(40, 10); check('height-to-history', range(-1, 5), 40, 10)
        resize(40, 12); check('height-restored', range(1, 7))
        phase('partial-up', '\x1b[3;5r\x1b[S')
        check('partial-up', [1, 2, 3, 5, 6])
        phase('partial-down', '\x1b[T')
        check('partial-down', [1, 3, 4, 5, 6])
        phase('overwrite-moved-strip', '\x1b[4;22H\x1b[X')
        check('overwrite-moved-strip', [1, 3, 4, 5, 6], erased=[(21, 3)])
        capture(hwnd, 'sixel-partial-scroll.png')
        phase('whole-region-delete', '\x1b[99S')
        check('whole-region-delete', [1, 5, 6])
        draw('history-setup')
        phase('into-history', '\x1b[12;1H\n\n')
        check('into-history', range(-1, 5))
        phase('clear-history', '\x1b[3J')
        check('clear-history-keeps-visible', range(5))
        phase('erase-all', '\x1b[2J')
        check('erase-all', [])
        draw('alt-main')
        phase('alt-enter', '\x1b[?1049h\x1b[H')
        check('alt-empty', [])
        phase('alt-image', '\x1b[2;21H'+solid(6*cw, 6*ch)+'\x1b[H')
        check('alt-image', range(1, 7))
        resize(30, 5); check('alt-height-clipped', range(1, 5), 30, 5)
        resize(40, 12); check('alt-height-no-resurrection', range(1, 5))
        phase('alt-exit', '\x1b[?1049l')
        check('main-height-no-resurrection', range(1, 5))
        draw('repeated-resize')
        for repeat in range(12):
            resize(24, 10); check(f'resize-small-{repeat}', range(1, 7), 24, 10)
            resize(40, 12); check(f'resize-large-{repeat}', range(1, 7))
        capture(hwnd, 'sixel-resize-retained.png')
        evidence.update(cell_pixels=[cw, ch],
                        peak_private_ws=max(s['private_ws'] for s in samples),
                        peak_total_ws=max(s['total_ws'] for s in samples),
                        peak_private_commit=max(s['private_commit'] for s in samples),
                        executable_sha256=hashlib.sha256((root/'dist/nemoterm.exe').read_bytes()).hexdigest())
        assert evidence['peak_private_ws'] < 20_000_000, evidence
        (root/'research/sixel-window-observed.json').write_text(json.dumps(evidence, indent=2))
        print('Native Sixel resize, scrolling, erasure and history passed:', evidence)
    finally:
        stop.set(); worker.join(2); k.CloseHandle(handle)
        write_snapshot(control, {'stop':True})
        process.wait(timeout=10)
