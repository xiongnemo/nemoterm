"""Compare XTWINOPS geometry with Win32 rectangles and rendered cell pixels."""
import argparse
import re
import uuid
import winreg
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, wait_for, read_snapshot, write_snapshot, wait_snapshot,
    find_window, memory_sample, capture, terminal_host, time)
from owned_job import OwnedJob
from automation_capture import OwnedAutomationCapture
from owned_failure_state import record_owned_failure

parser = argparse.ArgumentParser()
parser.add_argument('--font', default=os.environ.get('NEMOTERM_TEST_FONT',
    'Consolas' if os.environ.get('CI') == 'true' else 'SarasaTermSC Nerd Font Light'))
parser.add_argument('--renderer', type=int, choices=(0,1,2))
parser.add_argument('--observe', action='store_true')
parser.add_argument('--tabs',action='store_true')
parser.add_argument('--tab-side',choices=('top','bottom','left','right'),default='top')
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
u.GetDpiForWindow.argtypes, u.GetDpiForWindow.restype = [w.HWND], w.UINT

class MonitorInfo(c.Structure):
    _fields_ = [('size', w.DWORD), ('monitor', w.RECT), ('work', w.RECT), ('flags', w.DWORD)]

queries = '\x1b[11t\x1b[13t\x1b[13;2t\x1b[14t\x1b[14;2t\x1b[15t\x1b[16t\x1b[18t\x1b[19t'
queries += '\x1b]1337;ReportCellSize\x1b\\'
def drawing(colors):
    green, blue = (';'.join(map(str, color)) for color in colors)
    return ('\x1b[?25l\x1b[0m\x1b]11;#000000\x07\x1b[2J'
            f'\x1b[1;1H\x1b[48;2;{green}m  \x1b[0m'
            f'\x1b[3;4H\x1b[48;2;{blue}m \x1b[0m')
evidence = dict(tab_host=args.tabs,tab_side=args.tab_side,executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    requested_font=args.font, modes=[], runtime_files={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
    for p in (exe.parent/'OpenConsole.exe', exe.parent/'conpty.dll') if p.exists()})

try:
    for renderer in ((args.renderer,) if args.renderer is not None else (0, 1, 2)):
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
                process = job.spawn([str(exe), '--automation']+(['--tabs','--tab-side',args.tab_side] if args.tabs else [])+['-load', profile, '--cols', '80', '--rows', '24',
                    '--font-size', '12', '--font', args.font, '-e', sys.executable,
                    str(root/'tests/mouse_fixture.py'), str(report), str(control)],
                    env=dict(os.environ, NEMOTERM_CONPTY='bundled', NEMOTERM_TEST_UTF8_INPUT='1',
                             NEMOTERM_TEST_EXACT_OUTPUT='1'), creationflags=subprocess.CREATE_NO_WINDOW)
                mode['pid'] = process.pid
                handle = k.OpenProcess(0x410, False, process.pid)
                observer = None
                gl_capture = None
                try:
                    hwnd = wait_for(lambda: find_window(process.pid))
                    wait_for(lambda: read_snapshot(report))
                    mode['active_renderer'] = int(u.GetPropW(hwnd, 'NemotermRenderer') or 0)
                    assert mode['active_renderer'] in (1, 2, 3)
                    if renderer == 0: assert mode['active_renderer'] == 1
                    if renderer==1 and os.environ.get('NEMOTERM_REQUIRE_OPENGL') == '1':
                        assert mode['active_renderer'] == 2, 'OpenGL fell back'
                    if renderer==2 and os.environ.get('NEMOTERM_REQUIRE_DIRECTX') == '1':
                        assert mode['active_renderer'] == 3, 'DirectX fell back'
                    mode['memory_before_instrumentation'] = memory_sample(handle)
                    if mode['active_renderer'] in (2, 3):
                        gl_capture = OwnedAutomationCapture(process.pid, hwnd)
                    mode['capture_method'] = 'owned-automation-retained-frame' if gl_capture else 'PrintWindow'
                    mode['capture_instrumented'] = False
                    mode['memory_instrumented'] = bool(args.observe)
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
                        assert u.GetWindowRect(terminal_host(hwnd), c.byref(outer))
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
                        cell_reports = re.findall(
                            r'\x1b\]1337;ReportCellSize=([0-9]+\.[0-9]{3});([0-9]+\.[0-9]{3});([0-9]+\.[0-9]{3})\x1b\\', raw)
                        assert len(cell_reports) == 1, (name, raw)
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
                        expected = [[2 if u.IsIconic(terminal_host(hwnd)) else 1], [3,outer.left&65535,outer.top&65535],
                            [3,(origin.x+left)&65535,(origin.y+top)&65535], [4,value['rows']*ch,value['columns']*cw],
                            [4,outer.bottom-outer.top,outer.right-outer.left], [5,sh,sw], [6,ch,cw],
                            [8,value['rows'],value['columns']], [9,sh//ch,sw//cw]]
                        assert replies == expected, (name,replies,expected)
                        dpi = int(u.GetDpiForWindow(hwnd))
                        assert dpi > 0
                        logical_cell = list(map(float, cell_reports[0]))
                        logical_expected = [ch*96/dpi, cw*96/dpi, dpi/96]
                        assert all(abs(a-b) <= 0.000501 for a,b in zip(logical_cell,logical_expected)), \
                            (name, logical_cell, logical_expected, dpi)
                        assert int(u.GetPropW(hwnd, 'NemotermRenderer') or 0) == mode['active_renderer'], \
                            (name,'renderer changed during geometry operations')
                        sample = memory_sample(handle)
                        mode['checks'].append(dict(name=name, replies=replies, memory=sample,
                            iterm_cell_report=logical_cell, native_dpi=dpi,
                            cell=[cw,ch], text_offset=[left,top], child_grid=[value['columns'],value['rows']],
                            native_outer=[outer.left,outer.top,outer.right,outer.bottom]))
                        return outer, client, value

                    initial, _, _ = phase('initial', drawing(colors))
                    captured(f'geometry-{renderer}.png')
                    assert u.SetWindowPos(terminal_host(hwnd), None, -160, -90, 0, 0, 0x1|0x4|0x10)
                    phase('negative-position')
                    assert u.SetWindowPos(terminal_host(hwnd), None, 40, 40, 0, 0, 0x1|0x4|0x10)
                    current, _, grid = phase('relocated')
                    assert u.SetWindowPos(terminal_host(hwnd), None, 40, 40,
                        current.right-current.left+mode['cell'][0]*3,
                        current.bottom-current.top+mode['cell'][1]*2, 0x4|0x10)
                    wait_snapshot(lambda: read_snapshot(report), lambda v:
                        v.get('columns') == grid['columns']+3 and v.get('rows') == grid['rows']+2)
                    phase('resized-grid', drawing(colors))
                    u.ShowWindow(terminal_host(hwnd), 7)  # minimize only the owned window, without activation
                    wait_for(lambda: u.IsIconic(terminal_host(hwnd)))
                    # New pixels arrive while no drawing surface exists. Restore
                    # must display them without resending the scene afterwards.
                    colors = [(29,181,97), (31,79,223)]
                    phase('minimized', drawing(colors), pixels=False)
                    u.ShowWindow(terminal_host(hwnd), 9)
                    wait_for(lambda: not u.IsIconic(terminal_host(hwnd)))
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
                    close_started = time.monotonic()
                    try:
                        mode['exit_code'] = process.wait(timeout=10)
                    finally:
                        mode['close_seconds'] = time.monotonic()-close_started
                    assert mode['exit_code'] == 0, mode['exit_code']
                    mode['cleanup'] = job.finish(grace=5)
                    assert not mode['cleanup']['terminated_remaining'], mode['cleanup']
                except BaseException as error:
                    mode['error'] = repr(error)
                    record_owned_failure(process, job, mode, 'geometry-failure')
                    raise
                finally:
                    primary_failure = sys.exc_info()[0] is not None
                    try:
                        if gl_capture:
                            gl_capture.close()
                        if observer:
                            from frida_test_utils import detach_session
                            detach_session(observer)
                    except Exception as error:
                        mode['observer_cleanup_error'] = repr(error)
                        if not primary_failure:
                            raise
                    finally:
                        try:
                            mode['cleanup'] = job.finish(grace=0)
                            process.wait(timeout=5)
                        finally:
                            k.CloseHandle(handle)
        finally:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, keypath)
    evidence['completed'] = True
finally:
    if sys.exc_info()[0] is not None:
        evidence['error'] = repr(sys.exc_info()[1])
    (root/'research'/('tabs-geometry-window-observed.json' if args.tabs else 'geometry-window-observed.json')).write_text(json.dumps(evidence,indent=2),encoding='utf-8')
print('Native geometry queries passed:', [(m['active_renderer'],len(m['checks'])) for m in evidence['modes']])
