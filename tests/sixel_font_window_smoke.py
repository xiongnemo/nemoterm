"""Sixel raster/holes survive font changes in an own HWND and ConPTY child."""
import uuid
import winreg
import argparse
from contextlib import contextmanager
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, threading, time, read_snapshot, write_snapshot,
    memory_sample, wait_for, wait_snapshot, find_window, capture)

u.GetClientRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.GetGuiResources.argtypes, u.GetGuiResources.restype = [w.HANDLE, w.DWORD], w.DWORD
parser = argparse.ArgumentParser()
parser.add_argument('--font', default='SarasaTermSC Nerd Font Light')
args = parser.parse_args()
exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()

@contextmanager
def profile():
    name = 'native-sixel-font-' + uuid.uuid4().hex
    path = 'Software\\Nemo\\Nemoterm\\Sessions\\' + name
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
        winreg.SetValueEx(key, 'LockSize', 0, winreg.REG_DWORD, 2)
    try:
        yield name
    finally:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)

def solid(width, height):
    bands = ''.join(f'!{width}{chr(63+(1 << min(6, height-y))-1)}-'
                    for y in range(0, height, 6))
    return f'\x1bP0;1q"1;1;{width};{height}#1;2;100;0;0'+bands+'\x1b\\'

with profile() as profile_name, tempfile.TemporaryDirectory(prefix='nemoterm-sixel-font-') as directory:
    directory = Path(directory)
    report, control = directory/'report.json', directory/'control.json'
    process = subprocess.Popen([str(exe), '-load', profile_name,
        '--cols', '40', '--rows', '12', '--font', args.font, '--font-size', '12',
        '-e', sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control)],
        env=dict(os.environ, NEMOTERM_CONPTY='bundled'), creationflags=subprocess.CREATE_NO_WINDOW)
    handle = k.OpenProcess(0x410, False, process.pid)
    samples, stop, observations = [], threading.Event(), []
    def sample():
        while not stop.is_set():
            samples.append(memory_sample(handle))
            stop.wait(0.025)
    worker = threading.Thread(target=sample, daemon=True)
    worker.start()
    width, height, image_col = 96, 60, 3
    anchors, holes = [2]*height, set()
    def current():
        value = read_snapshot(report)
        assert not value.get('error') and process.poll() is None, value
        return value
    def phase(name, sequence=''):
        sequence += '\x1b[H\x1b[18t'
        write_snapshot(control, {'phase':name, 'sequence':sequence})
        return wait_snapshot(current, lambda v: v.get('phase') == name and
                             b'\x1b[8;12;40t' in bytes.fromhex(v.get('hex', '')))
    def read_pixels():
        rect = w.RECT(); u.GetClientRect(hwnd, c.byref(rect))
        pixels = capture(hwnd, return_pixels=True)
        red, green = set(), set()
        for i in range(0, len(pixels), 3):
            rgb = pixels[i:i+3]
            if rgb == b'\xff\0\0': red.add((i//3 % rect.right, i//3 // rect.right))
            elif rgb == b'\0\xff\0': green.add((i//3 % rect.right, i//3 // rect.right))
        assert green, 'missing steady green cursor used to measure the cell grid'
        xs, ys = [p[0] for p in green], [p[1] for p in green]
        geom = min(xs), min(ys), max(xs)-min(xs)+1, max(ys)-min(ys)+1
        return geom, red, (rect.right, rect.bottom)
    def check(name):
        last, expected, geom = set(), set(), None
        def matches():
            nonlocal last, expected, geom
            geom, last, _ = read_pixels()
            ox, oy, cw, ch = geom
            expected = {(ox+image_col*cw+x, oy+anchor*ch+y)
                        for y, anchor in enumerate(anchors) if anchor is not None
                        and 0 <= anchor*ch+y < 12*ch
                        for x in range(width) if (x, y) not in holes}
            return last == expected
        try:
            wait_for(matches)
        except AssertionError:
            capture(hwnd, 'sixel-font-failure.png')
            raise AssertionError((name, geom, len(expected), len(last),
                                  sorted(expected-last)[:6], sorted(last-expected)[:6]))
        observations.append(dict(phase=name, geometry=geom, red_pixels=len(last),
                                 gdi=u.GetGuiResources(handle, 0)))
        return geom
    def resize(name, sx, sy):
        assert u.MoveWindow(hwnd, 10, 10,
            outer.right-outer.left + round((sx-1)*(client.right-2)),
            outer.bottom-outer.top + round((sy-1)*(client.bottom-2)), True)
        phase(name)
        return check(name)
    def erase(name, col, row):
        _, _, cw, ch = read_pixels()[0]
        for y, anchor in enumerate(anchors):
            if anchor is not None and row*ch <= anchor*ch+y < (row+1)*ch:
                holes.update((x, y) for x in range(width)
                             if col*cw <= image_col*cw+x < (col+1)*cw)
        phase(name, f'\x1b[{row+1};{col+1}H\x1b[X')
        check(name)
    try:
        hwnd = wait_for(lambda: find_window(process.pid))
        wait_snapshot(current, lambda v: v.get('columns') == 40)
        outer, client = w.RECT(), w.RECT()
        u.GetWindowRect(hwnd, c.byref(outer)); u.GetClientRect(hwnd, c.byref(client))
        phase('initial', '\x1b[?80l\x1b[0m\x1b[r\x1b[2J\x1b[3J'
              '\x1b]11;rgb:0/0/0\x07\x1b]12;rgb:0/f/0\x07\x1b[2 q\x1b[?25h'
              '\x1b[3;4H'+solid(width, height))
        base = check('initial')
        erase('initial-hole', 4, 2)
        initial_pixels = observations[-1]['red_pixels']
        capture(hwnd, 'sixel-font-before.png')
        for name, sx, sy in [('wide', 2, 1), ('tall', 1, 2), ('both', 1.5, 1.5)]:
            geom = resize(name, sx, sy)
            assert observations[-1]['red_pixels'] == initial_pixels, observations[-1]
            assert abs(geom[2]-base[2]*sx) <= 1 and abs(geom[3]-base[3]*sy) <= 1, geom
        capture(hwnd, 'sixel-font-enlarged.png')
        erase('new-grid-hole', 5, 3)
        resize('restored-with-holes', 1, 1)
        assert observations[-1]['geometry'] == base, (base, observations)
        # A partial scroll applies to the current physical text rows; retain
        # each surviving source pixel and its character-unit translation.
        ch = base[3]
        for y, anchor in enumerate(anchors):
            if anchor is not None and 3 <= (anchor*ch+y)//ch <= 4:
                dest = (anchor*ch+y)//ch - 1
                anchors[y] = anchor-1 if 3 <= dest <= 4 else None
        phase('partial-scroll', '\x1b[4;5r\x1b[S')
        check('partial-scroll')
        for repeat in range(8):
            resize(f'split-tall-{repeat}', 1, 2)
            resize(f'split-restore-{repeat}', 1, 1)
        capture(hwnd, 'sixel-font-split-restored.png')
        phase('into-history', '\x1b[r\x1b[12;1H\n\n\n')
        anchors = [None if anchor is None else anchor-3 for anchor in anchors]
        check('into-history')
        anchors = [anchor if anchor is not None and anchor*ch+y >= 0 else None
                   for y, anchor in enumerate(anchors)]
        phase('clear-history', '\x1b[3J')
        check('clear-history-keeps-visible')
        phase('clear-image', '\x1b[2J'); anchors = [None]*height
        check('clear-image')
        # Distinct image widths make main/alternate preservation observable.
        width, anchors, holes = 96, [2]*height, set()
        phase('main-new', '\x1b[3;4H'+solid(width, height)); check('main-new')
        phase('alt-empty', '\x1b[?1049h'); anchors = [None]*height
        check('alt-empty')
        width, anchors = 48, [2]*height
        phase('alt-new', '\x1b[3;4H'+solid(width, height)); check('alt-new')
        resize('alt-wide', 2, 1)
        width = 96
        phase('main-restored-wide', '\x1b[?1049l'); check('main-restored-wide')
        resize('main-final-size', 1, 1)
        # Exercise the shared 4 MiB budget with real decoder/tile/mask heap
        # allocations. Identical placements keep the pixel oracle exact even
        # when oldest images are evicted. Core tests verify the actual count.
        width, height, anchors, holes = 32, 32, [2]*32, set()
        phase('image-budget', '\x1b[2J\x1b[3J'+800*('\x1b[3;4H'+solid(32, 32)))
        check('image-budget')
        erase('image-budget-erase', 4, 2)
        resize('image-budget-font-change', 2, 2)
        anchors = [None]*height
        phase('image-budget-release', '\x1b[2J\x1b[3J')
        check('image-budget-release')
        assert observations[-1]['gdi'] <= observations[0]['gdi']+4, observations
        result = dict(observations=observations,
                      peak_private_ws=max(s['private_ws'] for s in samples),
                      peak_total_ws=max(s['total_ws'] for s in samples),
                      peak_private_commit=max(s['private_commit'] for s in samples),
                      executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest())
        assert result['peak_private_ws'] < 20_000_000, result
        (root/'research/sixel-font-observed.json').write_text(json.dumps(result, indent=2))
        print('Native Sixel font/raster/erase/scroll/history/screen checks passed:', result)
    finally:
        (root/'research/sixel-font-last-observations.json').write_text(json.dumps(dict(
            observations=observations, requested_font=args.font,
            executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest()), indent=2))
        stop.set(); worker.join(2); k.CloseHandle(handle)
        write_snapshot(control, {'stop':True})
        process.wait(timeout=10)
