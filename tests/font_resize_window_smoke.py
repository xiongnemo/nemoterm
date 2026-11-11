"""Check actual glyphs when a window resize changes the font, not its grid."""
import uuid
import winreg
from contextlib import contextmanager
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, time, read_snapshot, write_snapshot, memory_sample,
    wait_for, find_window, capture)

u.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.GetClientRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.GetGuiResources.argtypes, u.GetGuiResources.restype = [w.HANDLE, w.DWORD], w.DWORD

@contextmanager
def font_resize_profile():
    name = 'native-font-resize-' + uuid.uuid4().hex
    path = 'Software\\Nemo\\Nemoterm\\Sessions\\' + name
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
        winreg.SetValueEx(key, 'LockSize', 0, winreg.REG_DWORD, 2)  # RESIZE_FONT
    try:
        yield name
    finally:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)

with font_resize_profile() as profile, tempfile.TemporaryDirectory(prefix='nemoterm-font-') as directory:
    directory = Path(directory)
    report, control = directory/'report.json', directory/'control.json'
    process = subprocess.Popen([str(root/'dist/nemoterm.exe'), '-load', profile,
        '--cols', '40', '--rows', '12', '--font-size', '12',
        '-e', sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control)],
        env=dict(os.environ, NEMOTERM_CONPTY='bundled'), creationflags=subprocess.CREATE_NO_WINDOW)
    handle = k.OpenProcess(0x410, False, process.pid)
    evidence = []
    def current():
        value = read_snapshot(report)
        assert not value.get('error') and process.poll() is None, value
        return value
    def phase(name, sgr, text):
        sequence = ('\x1b[0m\x1b[?25l\x1b]10;rgb:f/f/f\x07'
                    '\x1b]11;rgb:0/0/0\x07\x1b[2J\x1b[2;2H'
                    '\x1b['+sgr+'m'+text+'\x1b[?2026$p')
        write_snapshot(control, {'phase':name, 'sequence':sequence})
        wait_for(lambda: current().get('phase') == name and
                 b'\x1b[?2026;2$y' in bytes.fromhex(current().get('hex', '')))
        time.sleep(0.08)
        assert (current()['columns'], current()['rows']) == (40, 12), current()
        return capture(hwnd, return_pixels=True)
    def measure(name):
        blank = phase(name+'-blank', '0', '')
        rect = w.RECT()
        u.GetClientRect(hwnd, c.byref(rect))
        widths = []
        for style in ('0', '3'):
            pixels = phase(name+'-'+style, style, '中')
            xs = [i//3 % rect.right for i in range(0, len(pixels), 3)
                  if pixels[i:i+3] != blank[i:i+3] and max(pixels[i:i+3]) > 64]
            assert xs, 'CJK glyph is invisible'
            widths.append(max(xs)-min(xs)+1)
        evidence.append(dict(phase=name, client=[rect.right, rect.bottom],
            widths=widths, memory=memory_sample(handle), gdi=u.GetGuiResources(handle, 0)))
        assert widths[1] >= widths[0]-1, ('italic glyph squeezed', evidence[-1])
        return widths
    try:
        hwnd = wait_for(lambda: find_window(process.pid))
        wait_for(current)
        outer, client = w.RECT(), w.RECT()
        u.GetWindowRect(hwnd, c.byref(outer))
        u.GetClientRect(hwnd, c.byref(client))
        base = measure('initial')
        capture(hwnd, 'font-resize-before.png')
        # Stretching only the width isolates the GDI average-width/grid-width
        # confusion; increasing the height exercises the font mapper too.
        for name, sx, sy in [('wide', 2, 1), ('tall', 1, 2), ('both', 1.5, 1.5), ('restore', 1, 1)]:
            assert u.MoveWindow(hwnd, 10, 10,
                outer.right-outer.left + round((sx-1)*(client.right-2)),
                outer.bottom-outer.top + round((sy-1)*(client.bottom-2)), True)
            widths = measure(name)
            for index in range(2):
                assert abs(widths[index]-base[index]*sx) <= 3, ('font scale mismatch', base, evidence[-1])
            if name == 'wide':
                capture(hwnd, 'font-resize-wide.png')
        assert evidence[-1]['gdi'] <= evidence[0]['gdi']+4, evidence
        result = dict(observations=evidence,
            executable_sha256=hashlib.sha256((root/'dist/nemoterm.exe').read_bytes()).hexdigest())
        (root/'research/font-resize-observed.json').write_text(json.dumps(result, indent=2))
        assert max(item['memory']['private_ws'] for item in evidence) < 20_000_000, evidence
        print('Native font resize passed:', result)
    finally:
        k.CloseHandle(handle)
        write_snapshot(control, {'stop': True})
        process.wait(timeout=10)
