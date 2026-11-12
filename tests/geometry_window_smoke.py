"""Compare XTWINOPS geometry with Win32 rectangles and rendered cell pixels."""
import argparse
import re
import uuid
import winreg
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, wait_for, read_snapshot, write_snapshot, wait_snapshot,
    find_window, memory_sample, capture)
from owned_job import OwnedJob
from gl_capture import OwnedGLCapture

parser = argparse.ArgumentParser()
parser.add_argument('--font', default=os.environ.get('NEMOTERM_TEST_FONT',
    'Consolas' if os.environ.get('CI') == 'true' else 'SarasaTermSC Nerd Font Light'))
parser.add_argument('--renderer', type=int, choices=(0,1))
parser.add_argument('--observe', action='store_true')
args = parser.parse_args()
exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
u.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.GetClientRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.ClientToScreen.argtypes = [w.HWND, c.POINTER(w.POINT)]
u.SetWindowPos.argtypes = [w.HWND, w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT]
u.ShowWindow.argtypes = [w.HWND, c.c_int]
u.IsIconic.argtypes = [w.HWND]
u.MonitorFromWindow.argtypes, u.MonitorFromWindow.restype = [w.HWND, w.DWORD], w.HANDLE
u.GetMonitorInfoW.argtypes = [w.HANDLE, c.c_void_p]
u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE

class MonitorInfo(c.Structure):
    _fields_ = [('size', w.DWORD), ('monitor', w.RECT), ('work', w.RECT), ('flags', w.DWORD)]

queries = '\x1b[11t\x1b[13t\x1b[13;2t\x1b[14t\x1b[14;2t\x1b[15t\x1b[16t\x1b[18t\x1b[19t'
def drawing(colors):
    green, blue = (';'.join(map(str, color)) for color in colors)
    return ('\x1b[?25l\x1b[0m\x1b]11;#000000\x07\x1b[2J'
            f'\x1b[1;1H\x1b[48;2;{green}m  \x1b[0m'
            f'\x1b[3;4H\x1b[48;2;{blue}m \x1b[0m')
evidence = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    requested_font=args.font, modes=[], runtime_files={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
    for p in (exe.parent/'OpenConsole.exe', exe.parent/'conpty.dll') if p.exists()})

try:
    for renderer in ((args.renderer,) if args.renderer is not None else (0, 1)):
        profile = 'geometry-'+uuid.uuid4().hex
        keypath = 'Software\\Nemo\\Nemoterm\\Sessions\\'+profile
        mode = dict(requested_renderer=renderer, checks=[])
        colors = [(17,201,83), (23,67,219)]
        evidence['modes'].append(mode)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, keypath) as key:
            for name, value in dict(WarnOnClose=0, NemoRenderer=renderer, LockSize=0).items():
                winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
        try:
            with tempfile.TemporaryDirectory(prefix='nemoterm-geometry-') as tmp, OwnedJob() as job:
                report, control = Path(tmp)/'report', Path(tmp)/'control'
                process = job.spawn([str(exe), '-load', profile, '--cols', '80', '--rows', '24',
                    '--font-size', '12', '--font', args.font, '-e', sys.executable,
                    str(root/'tests/mouse_fixture.py'), str(report), str(control)],
                    env=dict(os.environ, NEMOTERM_CONPTY='bundled', NEMOTERM_TEST_UTF8_INPUT='1',
                             NEMOTERM_TEST_EXACT_OUTPUT='1'), creationflags=subprocess.CREATE_NO_WINDOW)
                handle = k.OpenProcess(0x410, False, process.pid)
                observer = None
                gl_capture = None
                try:
                    hwnd = wait_for(lambda: find_window(process.pid))
                    wait_for(lambda: read_snapshot(report))
                    mode['active_renderer'] = int(u.GetPropW(hwnd, 'NemotermRenderer') or 0)
                    assert mode['active_renderer'] in (1, 2)
                    if renderer == 0: assert mode['active_renderer'] == 1
                    if renderer and os.environ.get('NEMOTERM_REQUIRE_OPENGL') == '1':
                        assert mode['active_renderer'] == 2, 'OpenGL fell back'
                    mode['memory_before_instrumentation'] = memory_sample(handle)
                    if mode['active_renderer'] == 2:
                        gl_capture = OwnedGLCapture(process.pid, hwnd)
                    mode['capture_method'] = 'owned-process-retained-frame' if gl_capture else 'PrintWindow'
                    mode['memory_instrumented'] = bool(gl_capture or args.observe)
                    if args.observe:
                        import frida
                        observer = frida.attach(process.pid)
                        source = 'const ownedWindow=ptr("'+hex(hwnd)+'");\n'
                        source += (root/'tests/geometry_gl_probe.js').read_text()
                        probe = observer.create_script(source)
                        mode['probe'] = []
                        probe.on('message', lambda message, data: mode['probe'].append(message))
                        probe.load()

                    def captured(name=None):
                        if gl_capture:
                            return gl_capture.capture(name, True)
                        return capture(hwnd, name, True)

                    def snapshot():
                        outer, client, origin, monitor = w.RECT(), w.RECT(), w.POINT(), MonitorInfo()
                        monitor.size = c.sizeof(monitor)
                        assert u.GetWindowRect(hwnd, c.byref(outer))
                        assert u.GetClientRect(hwnd, c.byref(client))
                        assert u.ClientToScreen(hwnd, c.byref(origin))
                        assert u.GetMonitorInfoW(u.MonitorFromWindow(hwnd, 2), c.byref(monitor))
                        return outer, client, origin, monitor.monitor

                    def phase(name, prefix='', pixels=True):
                        write_snapshot(control, dict(phase=name, sequence=prefix+queries+'\x1b[5n'))
                        value = wait_snapshot(lambda: read_snapshot(report), lambda v:
                            v.get('phase') == name and bytes.fromhex(v.get('hex', '')).endswith(b'\x1b[0n'))
                        raw = bytes.fromhex(value['hex']).decode('ascii')
                        replies = [list(map(int, x.split(';'))) for x in re.findall('\x1b\\[([0-9;-]+)t', raw)]
                        assert len(replies) == 9, (name, raw)
                        outer, client, origin, monitor = snapshot()
                        if pixels:
                            def pixel_geometry():
                                image = captured()
                                boxes = []
                                for color in map(bytes, colors):
                                    offsets = [i//3 for i in range(0,len(image),3) if image[i:i+3] == color]
                                    if not offsets: return None
                                    xs = [i % client.right for i in offsets]
                                    ys = [i // client.right for i in offsets]
                                    boxes.append([min(xs),min(ys),max(xs)+1,max(ys)+1])
                                return boxes
                            try:
                                boxes = wait_for(pixel_geometry)
                            except AssertionError:
                                from collections import Counter
                                image = captured(f'geometry-failure-{renderer}.png')
                                counts = Counter(image[i:i+3] for i in range(0,len(image),3))
                                mode['pixel_failure_colors'] = [(list(color),count) for color,count in counts.most_common(8)]
                                mode['renderer_after_failure'] = int(u.GetPropW(hwnd, 'NemotermRenderer') or 0)
                                raise
                            left, top, right, bottom = boxes[0]
                            assert (right-left) % 2 == 0
                            cw, ch = (right-left)//2, bottom-top
                            assert boxes[1] == [left+3*cw,top+2*ch,left+4*cw,top+3*ch], boxes
                            mode['cell'] = [cw, ch]
                            mode['offset'] = [left, top]
                        else:
                            cw, ch = mode['cell']
                            left, top = mode['offset']
                        sw, sh = monitor.right-monitor.left, monitor.bottom-monitor.top
                        expected = [[2 if u.IsIconic(hwnd) else 1], [3,outer.left&65535,outer.top&65535],
                            [3,(origin.x+left)&65535,(origin.y+top)&65535], [4,value['rows']*ch,value['columns']*cw],
                            [4,outer.bottom-outer.top,outer.right-outer.left], [5,sh,sw], [6,ch,cw],
                            [8,value['rows'],value['columns']], [9,sh//ch,sw//cw]]
                        assert replies == expected, (name,replies,expected)
                        assert int(u.GetPropW(hwnd, 'NemotermRenderer') or 0) == mode['active_renderer'], \
                            (name,'renderer changed during geometry operations')
                        sample = memory_sample(handle)
                        mode['checks'].append(dict(name=name, replies=replies, memory=sample,
                            cell=[cw,ch], text_offset=[left,top], child_grid=[value['columns'],value['rows']],
                            native_outer=[outer.left,outer.top,outer.right,outer.bottom]))
                        return outer, client, value

                    initial, _, _ = phase('initial', drawing(colors))
                    captured(f'geometry-{renderer}.png')
                    assert u.SetWindowPos(hwnd, None, -160, -90, 0, 0, 0x1|0x4|0x10)
                    phase('negative-position')
                    assert u.SetWindowPos(hwnd, None, 40, 40, 0, 0, 0x1|0x4|0x10)
                    current, _, grid = phase('relocated')
                    assert u.SetWindowPos(hwnd, None, 40, 40,
                        current.right-current.left+mode['cell'][0]*3,
                        current.bottom-current.top+mode['cell'][1]*2, 0x4|0x10)
                    wait_snapshot(lambda: read_snapshot(report), lambda v:
                        v.get('columns') == grid['columns']+3 and v.get('rows') == grid['rows']+2)
                    phase('resized-grid', drawing(colors))
                    u.ShowWindow(hwnd, 7)  # minimize only the owned window, without activation
                    wait_for(lambda: u.IsIconic(hwnd))
                    # New pixels arrive while no drawing surface exists. Restore
                    # must display them without resending the scene afterwards.
                    colors = [(29,181,97), (31,79,223)]
                    phase('minimized', drawing(colors), pixels=False)
                    u.ShowWindow(hwnd, 9)
                    wait_for(lambda: not u.IsIconic(hwnd))
                    phase('restored')
                    mode['output_while_minimized_preserved'] = True
                    phase('synchronized-queries', '\x1b[?2026h', pixels=False)
                    write_snapshot(control, dict(phase='sync-state', sequence='\x1b[?2026$p\x1b[?2026l\x1b[5n'))
                    value = wait_snapshot(lambda: read_snapshot(report), lambda v:
                        v.get('phase') == 'sync-state' and bytes.fromhex(v.get('hex','')).endswith(b'\x1b[0n'))
                    assert bytes.fromhex(value['hex']) == b'\x1b[?2026;1$y\x1b[0n', value
                    if mode['active_renderer'] == 1 and not mode['memory_instrumented']:
                        assert max(v['memory']['private_ws'] for v in mode['checks']) < 20_000_000
                    write_snapshot(control, dict(stop=True))
                    assert process.wait(timeout=10) == 0
                finally:
                    if gl_capture:
                        gl_capture.close()
                    if observer:
                        observer.detach()
                    job.finish(grace=0)
                    process.wait(timeout=5)
                    k.CloseHandle(handle)
        finally:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, keypath)
    evidence['completed'] = True
finally:
    if sys.exc_info()[0] is not None:
        evidence['error'] = repr(sys.exc_info()[1])
    (root/'research/geometry-window-observed.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
print('Native geometry queries passed:', [(m['active_renderer'],len(m['checks'])) for m in evidence['modes']])
