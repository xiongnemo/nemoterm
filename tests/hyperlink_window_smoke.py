"""OSC 8 hover/activation through an own HWND, ConPTY and temporary URI handler."""
import uuid
import winreg
import re
from contextlib import contextmanager
from clipboard_test_utils import SavedClipboard, clipboard_text
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, threading, time, read_snapshot, write_snapshot,
    memory_sample, wait_for, wait_snapshot, find_window, capture)

u.GetClientRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.ClientToScreen.argtypes = [w.HWND, c.POINTER(w.POINT)]
u.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, c.c_int]
u.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, c.c_int]
u.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
u.IsWindowVisible.argtypes = [w.HWND]
u.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
u.SetWindowPos.argtypes = [w.HWND, w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT]

def align_pointer(hwnd, x, y):
    # TrackMouseEvent uses the real desktop hit test. Keep only our test
    # window above other windows and under the existing cursor, without
    # activation or any global pointer/key injection.
    assert u.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x13)
    cursor, origin, outer = w.POINT(), w.POINT(), w.RECT()
    u.GetCursorPos(c.byref(cursor)); u.ClientToScreen(hwnd, c.byref(origin))
    u.GetWindowRect(hwnd, c.byref(outer))
    dx, dy = cursor.x-origin.x-x, cursor.y-origin.y-y
    if dx or dy:
        assert u.MoveWindow(hwnd, outer.left+dx, outer.top+dy,
                            outer.right-outer.left, outer.bottom-outer.top, True)

class GuiThreadInfo(c.Structure):
    _fields_ = [('cbSize', w.DWORD), ('flags', w.DWORD)] + [(name, w.HWND) for name in
        ('active','focus','capture','menu','move_size','caret')] + [('caret_rect', w.RECT)]
u.GetGUIThreadInfo.argtypes = [w.DWORD, c.POINTER(GuiThreadInfo)]

def gui_state(hwnd):
    state = GuiThreadInfo(cbSize=c.sizeof(GuiThreadInfo))
    assert u.GetGUIThreadInfo(u.GetWindowThreadProcessId(hwnd, None), c.byref(state))
    return state

class MenuBarInfo(c.Structure):
    _fields_ = [('cbSize', w.DWORD), ('rect', w.RECT), ('menu', w.HANDLE),
                ('window', w.HWND), ('flags', w.DWORD)]
u.GetMenuBarInfo.argtypes = [w.HWND, w.LONG, w.LONG, c.POINTER(MenuBarInfo)]
u.GetMenuState.argtypes = [w.HANDLE, w.UINT, w.UINT]
u.GetMenuStringW.argtypes = [w.HANDLE, w.UINT, w.LPWSTR, c.c_int, w.UINT]
u.GetMenuItemCount.argtypes = [w.HANDLE]

def popup_menu(pid):
    result = []
    @c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def visit(hwnd, _):
        owner, cls = w.DWORD(), c.create_unicode_buffer(64)
        u.GetWindowThreadProcessId(hwnd, c.byref(owner)); u.GetClassNameW(hwnd, cls, len(cls))
        if owner.value == pid and cls.value == '#32768' and u.IsWindowVisible(hwnd):
            info = MenuBarInfo(cbSize=c.sizeof(MenuBarInfo))
            assert u.GetMenuBarInfo(hwnd, -4, 0, c.byref(info))
            items = []
            for index in range(u.GetMenuItemCount(info.menu)):
                text = c.create_unicode_buffer(256)
                u.GetMenuStringW(info.menu, index, text, len(text), 0x400)
                items.append((text.value, u.GetMenuState(info.menu, index, 0x400)))
            result.append((hwnd, items))
        return True
    u.EnumWindows(visit, 0)
    return result[0] if len(result) == 1 else None

@contextmanager
def settings(directory, custom=True, disabled=False):
    scheme = 'nemoterm-test-' + uuid.uuid4().hex
    profile = 'native-hyperlink-' + uuid.uuid4().hex
    profile_path = 'Software\\Nemo\\Nemoterm\\Sessions\\' + profile
    scheme_path = 'Software\\Classes\\' + scheme
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    assert pythonw.is_file(), pythonw
    command = subprocess.list2cmdline([str(pythonw), str(root/'tests/hyperlink_target.py'),
                                       str(directory), '%1'])
    # list2cmdline does not quote %1 without spaces: the expanded URI must be
    # one argument even if Windows decodes %20 before invoking the handler.
    command = command[:-2] + '"%1"'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, profile_path) as key:
        if custom:
            winreg.SetValueEx(key, 'NemoCustomURLSchemes', 0, winreg.REG_DWORD, 1)
        if disabled:
            winreg.SetValueEx(key, 'NoRemoteHyperlinks', 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, 'WarnOnClose', 0, winreg.REG_DWORD, 0)
        if os.environ.get('NEMOTERM_TEST_LOG'):
            winreg.SetValueEx(key, 'LogType', 0, winreg.REG_DWORD, 2)
            winreg.SetValueEx(key, 'LogFileClash', 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, 'LogFileName', 0, winreg.REG_SZ, str(root/'build/hyperlink-conpty.log'))
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, scheme_path) as key:
        winreg.SetValueEx(key, '', 0, winreg.REG_SZ, 'Nemoterm test URI')
        winreg.SetValueEx(key, 'URL Protocol', 0, winreg.REG_SZ, '')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, scheme_path+'\\shell\\open\\command') as key:
        winreg.SetValueEx(key, '', 0, winreg.REG_SZ, command)
    try:
        yield scheme, profile
    finally:
        for suffix in ('\\shell\\open\\command', '\\shell\\open', '\\shell', ''):
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, scheme_path+suffix)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, profile_path)

def tooltip(pid):
    matches = []
    @c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def visit(hwnd, _):
        owner, cls = w.DWORD(), c.create_unicode_buffer(64)
        u.GetWindowThreadProcessId(hwnd, c.byref(owner))
        u.GetClassNameW(hwnd, cls, len(cls))
        if owner.value == pid and cls.value.lower() == 'static' and u.IsWindowVisible(hwnd):
            text = c.create_unicode_buffer(8192)
            u.GetWindowTextW(hwnd, text, len(text))
            matches.append((hwnd, text.value))
        return True
    u.EnumWindows(visit, 0)
    return matches[0] if len(matches) == 1 else None

def preference_checks():
    evidence = {}
    for disabled in (False, True):
        with tempfile.TemporaryDirectory(prefix='nemoterm-link-policy-') as directory:
            directory = Path(directory)
            launches = directory/'launches'; launches.mkdir()
            with settings(launches, custom=disabled, disabled=disabled) as (scheme, profile):
                report, control = directory/'report.json', directory/'control.json'
                process = subprocess.Popen([str(root/'dist/nemoterm.exe'), '-load', profile,
                    '--cols', '40', '--rows', '8', '--right-click', 'copy-paste', '-e', sys.executable,
                    str(root/'tests/mouse_fixture.py'), str(report), str(control)],
                    env=dict(os.environ, NEMOTERM_CONPTY='bundled'),
                    creationflags=subprocess.CREATE_NO_WINDOW)
                hwnd = None
                try:
                    hwnd = wait_for(lambda: find_window(process.pid))
                    wait_for(lambda: read_snapshot(report))
                    rect = w.RECT()
                    u.GetClientRect(hwnd, c.byref(rect))
                    cw, ch = (rect.right-2)//40, (rect.bottom-2)//8
                    x, y = 1+2*cw+cw//2, 1+ch+ch//2
                    align_pointer(hwnd, x, y)
                    uri = scheme+'://host/'
                    uri += 'x' * (2083-len(uri))
                    def draw(name, target):
                        seq = '\x1b[?25l\x1b[2;2H\x1b]8;;'+target+'\x1b\\LINK\x1b]8;;\x1b\\'
                        write_snapshot(control, {'phase': name, 'sequence': seq+'\x1b[?1000$p'})
                        wait_snapshot(lambda: read_snapshot(report), lambda v:
                            v.get('phase') == name and '1b5b3f31303030' in v.get('hex', ''))
                        time.sleep(.08)
                    def hover_target(target):
                        def probe():
                            align_pointer(hwnd, x, y)
                            u.SendMessageW(hwnd, 0x200, 0, x | (y << 16))
                            tip = tooltip(process.pid)
                            return tip if tip and target in ''.join(tip[1].splitlines()) else None
                        return wait_for(probe)
                    draw('long-address', uri)
                    u.SendMessageW(hwnd, 0x200, 0, x | (y << 16))
                    if disabled:
                        time.sleep(.12)
                        assert tooltip(process.pid) is None
                    else:
                        tip, text = hover_target(uri)
                        assert 'scheme is disabled' in text, text
                        assert len(text.splitlines()) > 5
                        capture(tip, 'hyperlink-long-address.png')
                        evidence['long_address_bytes'] = len(uri)
                    u.SendMessageW(hwnd, 0x201, 9, x | (y << 16))
                    u.SendMessageW(hwnd, 0x202, 8, x | (y << 16))
                    time.sleep(.15)
                    assert not list(launches.glob('*.json'))
                    evidence['disabled' if disabled else 'custom_scheme_default_disabled'] = True
                    if not disabled:
                        # Existing pointer position must refresh when output replaces a link.
                        draw('https-default', 'https://example.invalid/never-opened')
                        _, text = hover_target('https://example.invalid/never-opened')
                        assert text.startswith('Ctrl+click to open;'), text
                        draw('replace-under-pointer', 'https://example.invalid/replaced')
                        _, text = wait_for(lambda: (tip := tooltip(process.pid)) and
                            'https://example.invalid/replaced' in ''.join(tip[1].splitlines()) and tip)
                        draw('clear-under-pointer', '')
                        wait_for(lambda: tooltip(process.pid) is None)
                        evidence['live_hover_refresh'] = True
                        draw('right-copy-paste', '')
                        start = (1+cw+cw//2) | (y << 16)
                        end = (1+4*cw+cw//2) | (y << 16)
                        u.SendMessageW(hwnd, 0x201, 5, start)
                        u.SendMessageW(hwnd, 0x200, 5, end)
                        u.SendMessageW(hwnd, 0x202, 4, end)
                        saved = SavedClipboard(hwnd)
                        try:
                            def right_copy_paste():
                                u.SendMessageW(hwnd, 0x204, 2, x | (y << 16))
                                u.SendMessageW(hwnd, 0x205, 0, x | (y << 16))
                            clipboard_contention(right_copy_paste, .4)
                            wait_snapshot(lambda: read_snapshot(report), lambda v:
                                b'LINK' in bytes.fromhex(v.get('hex', '')))
                            evidence['right_copy_paste_with_busy_clipboard'] = True
                        finally:
                            saved.restore()
                    assert process.poll() is None
                finally:
                    write_snapshot(control, {'stop': True})
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        if hwnd: u.PostMessageW(hwnd, 0x10, 0, 0)
                        try: process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.terminate(); process.wait(timeout=5)
                        raise
    return evidence

def clipboard_contention(action, duration):
    ready = threading.Event()
    failures = []
    def holder():
        try:
            wait_for(lambda: u.OpenClipboard(None))
            try:
                ready.set()
                time.sleep(duration)
            finally:
                u.CloseClipboard()
        except BaseException as error:
            failures.append(error)
            ready.set()
    thread = threading.Thread(target=holder)
    thread.start()
    try:
        assert ready.wait(8) and not failures, failures
        started = time.monotonic()
        action()
        elapsed = time.monotonic()-started
        # A still-held clipboard cannot prevent processing unrelated messages.
        return elapsed
    finally:
        thread.join(8)
        assert not thread.is_alive() and not failures, failures

preferences = preference_checks()

with tempfile.TemporaryDirectory(prefix='nemoterm-hyperlink-') as directory:
    directory = Path(directory)
    launches = directory/'launches'; launches.mkdir()
    with settings(launches) as (scheme, profile):
        report, control = directory/'report.json', directory/'control.json'
        process = subprocess.Popen([str(root/'dist/nemoterm.exe'), '-load', profile,
            '--cols', '40', '--rows', '12', '-e', sys.executable,
            str(root/'tests/mouse_fixture.py'), str(report), str(control)],
            env=dict(os.environ, NEMOTERM_CONPTY='bundled'), creationflags=subprocess.CREATE_NO_WINDOW)
        handle = k.OpenProcess(0x410, False, process.pid)
        evidence, samples, stop, clipboard, hwnd = {'preferences': preferences}, [], threading.Event(), None, None
        def sampler():
            while not stop.is_set():
                samples.append(memory_sample(handle)); stop.wait(.025)
        worker = threading.Thread(target=sampler, daemon=True); worker.start()
        def current():
            value = read_snapshot(report)
            assert not value.get('error') and process.poll() is None, value
            return value
        def phase(name, sequence, timeout=8):
            write_snapshot(control, {'phase': name, 'sequence': sequence+'\x1b[?1000$p'})
            wait_snapshot(current, lambda v: v.get('phase') == name and
                          b'\x1b[?1000;' in bytes.fromhex(v.get('hex', '')), timeout=timeout)
            time.sleep(.08)
        def msg(kind, col=2, row=1, keys=0):
            x, y = 1+col*cw+cw//2, 1+row*ch+ch//2
            return u.SendMessageW(hwnd, kind, keys, (x & 65535) | ((y & 65535) << 16))
        def link(uri, label, ident='group'):
            return f'\x1b]8;id={ident};{uri}\x1b\\{label}\x1b]8;;\x1b\\'
        def launched():
            return [read_snapshot(path) for path in sorted(launches.glob('*.json'))]
        def hover(uri):
            last = None
            def probe():
                nonlocal last
                align_pointer(hwnd, 1+2*cw+cw//2, 1+ch+ch//2)
                msg(0x200)
                tip = tooltip(process.pid)
                last = tip
                return tip if tip and uri in ''.join(tip[1].splitlines()) else None
            try:
                return wait_for(probe)
            except AssertionError:
                capture(hwnd, 'hyperlink-failed.png')
                raise AssertionError(('hover', uri, last, cw, ch, current()))
        def menu(index, can_open=True, clipboard_hold=0):
            # Put the owned popup away from the real pointer so desktop mouse
            # movement cannot replace its keyboard-selected menu item.
            cursor, outer = w.POINT(), w.RECT()
            u.GetCursorPos(c.byref(cursor)); u.GetWindowRect(hwnd, c.byref(outer))
            midpoint = u.GetSystemMetrics(0)//2
            assert u.MoveWindow(hwnd, midpoint if cursor.x < midpoint else 10, 20,
                                outer.right-outer.left, outer.bottom-outer.top, True)
            x, y = 1+2*cw+cw//2, 1+ch+ch//2
            assert u.PostMessageW(hwnd, 0x204, 10, x | (y << 16))
            wait_for(lambda: gui_state(hwnd).menu == hwnd)
            time.sleep(.12)  # let the popup finish layout before navigation
            visible = wait_for(lambda: popup_menu(process.pid))
            assert bool(visible[1][3][1] & 3) == (not can_open), visible
            assert not (visible[1][index][1] & 3), visible
            # Some Windows popup menus initially have no selected item; Home
            # need not select item zero. Navigate against the actual highlight.
            for attempt in range(len(visible[1])+1):
                visible = popup_menu(process.pid)
                if visible and visible[1][index][1] & 0x80: break
                assert u.PostMessageW(hwnd, 0x100, 0x28, 1)
                assert u.PostMessageW(hwnd, 0x101, 0x28, 0xc0000001)
                time.sleep(.025)
            assert visible and visible[1][index][1] & 0x80, visible
            def accept():
                assert u.PostMessageW(hwnd, 0x100, 0x0d, 1)
                assert u.PostMessageW(hwnd, 0x101, 0x0d, 0xc0000001)
                wait_for(lambda: gui_state(hwnd).menu != hwnd)
                msg(0x205, keys=8)
            if clipboard_hold:
                clipboard_contention(accept, clipboard_hold)
            else:
                accept()
        def data():
            time.sleep(.06)
            return bytes.fromhex(wait_snapshot(current, lambda v: 'hex' in v)['hex'])
        try:
            hwnd = wait_for(lambda: find_window(process.pid))
            clipboard = SavedClipboard(hwnd)
            wait_for(current)
            rect = w.RECT(); u.GetClientRect(hwnd, c.byref(rect))
            cw, ch = (rect.right-2)//40, (rect.bottom-2)//12
            # Keep the baseline away from the existing pointer. A synthetic
            # WM_MOUSELEAVE alone cannot prevent a real hover refresh, and its
            # underline removal can still be waiting for deferred painting.
            cursor, outer = w.POINT(), w.RECT()
            u.GetCursorPos(c.byref(cursor)); u.GetWindowRect(hwnd,c.byref(outer))
            width,height=outer.right-outer.left,outer.bottom-outer.top
            # Keep it on screen as well: an off-screen DWM surface can retain
            # the startup cursor even after the text rows have been painted.
            screen_width = u.GetSystemMetrics(0)
            park_x = max(0, screen_width-width-20) if cursor.x < screen_width//2 else 20
            assert u.MoveWindow(hwnd,park_x,20,width,height,True)
            uri = scheme + '://host/path?x=one%20two&y=%22quoted%22#part'
            other = scheme + '://host/other'
            scene = '\x1b[0m\x1b[?25l\x1b[2J\x1b[2;2H' + link(uri, 'LINK')
            scene += '\x1b[2;11H' + link(uri, 'MORE') + '\x1b[2;21H' + link(other, 'ELSE')
            phase('plain-labels','\x1b[0m\x1b[?25l\x1b[2J\x1b[2;2HLINK'
                  '\x1b[2;11HMORE\x1b[2;21HELSE')
            def painted_baseline():
                u.SendMessageW(hwnd, 0x2a3, 0, 0)  # own-window WM_MOUSELEAVE
                pixels = capture(hwnd, return_pixels=True)
                background = pixels[:3]
                if any(pixels[i:i+3] != background for i in range(0, rect.right*ch*3, 3)):
                    return None  # hidden startup cursor must also be erased
                # The query reply acknowledges parser state, not its deferred
                # paint. Require all three labels before comparing hover pixels.
                for lo,hi in ((1,5),(10,14),(20,24)):
                    if not any(pixels[3*(y*rect.right+x):3*(y*rect.right+x)+3] != background
                               for y in range(1+ch,1+2*ch-2)
                               for x in range(1+lo*cw,1+hi*cw)):
                        return None
                return pixels
            baseline = wait_for(painted_baseline)
            phase('labels', scene)
            # Adding OSC 8 metadata while not hovered must leave all pixels
            # unchanged. Only then exercise hover and compare the underline.
            wait_for(lambda:capture(hwnd,return_pixels=True)==baseline)
            capture(hwnd, 'hyperlink-baseline.png')
            tip, text = hover(uri)
            evidence['hover_text'] = text
            selected = wait_for(lambda: (pixels := capture(hwnd, return_pixels=True)) != baseline and pixels)
            changed = [i//3 for i in range(0, len(selected), 3) if selected[i:i+3] != baseline[i:i+3]]
            bounds = [min(i%rect.right for i in changed), min(i//rect.right for i in changed),
                      max(i%rect.right for i in changed)+1, max(i//rect.right for i in changed)+1]
            evidence['hover_bounds'] = bounds
            capture(hwnd, 'hyperlink-hover.png'); capture(tip, 'hyperlink-address.png')
            expected = {bounds[1]*rect.right+x for lo,hi in ((1,5),(10,14))
                        for x in range(1+lo*cw,1+hi*cw)}
            assert bounds[3]-bounds[1] == 1 and set(changed) == expected, bounds
            msg(0x201, keys=9); msg(0x202, keys=8)
            observed = wait_for(lambda: (data := launched()) and data)
            assert len(observed) == 1 and observed[0]['argv'] == [uri], observed
            evidence['opened'] = observed[0]['argv']
            for mode in (1000, 1001, 1002, 1003):
                phase('mouse-'+str(mode), scene+f'\x1b[?{mode};1006h')
                before = len(launched())
                msg(0x201, keys=9); msg(0x202, keys=8)
                wait_for(lambda: len(launched()) == before+1)
                value = wait_snapshot(current, lambda v: 'hex' in v)
                reports = re.findall(rb'\x1b\[<(\d+);(\d+);(\d+)([Mm])', bytes.fromhex(value['hex']))
                assert all(mode == 1003 and r == (b'35', b'3', b'2', b'M') for r in reports), value
                evidence['mouse-'+str(mode)] = value['hex']
            phase('menu-copy', scene)
            menu(4)
            wait_for(lambda: clipboard_text(hwnd) == uri)
            evidence['copied_address'] = uri
            before = len(launched()); menu(3)
            wait_for(lambda: len(launched()) == before+1)
            evidence['menu_open'] = True

            # WM_CANCELMODE must also reach DefWindowProc to end menu mode.
            x, y = 1+2*cw+cw//2, 1+ch+ch//2
            assert u.PostMessageW(hwnd, 0x204, 10, x | (y << 16))
            wait_for(lambda: gui_state(hwnd).menu == hwnd)
            assert u.PostMessageW(hwnd, 0x1f, 0, 0)
            wait_for(lambda: gui_state(hwnd).menu != hwnd)
            msg(0x205, keys=8)
            evidence['menu_cancel'] = True

            # Shift always selects the displayed label; ordinary right-click
            # copies it without opening a link or pasting into the child.
            phase('shift', scene+'\x1b[?1003;1006h')
            before = len(launched())
            msg(0x201, col=1, keys=5); msg(0x200, col=4, keys=5); msg(0x202, col=4, keys=4)
            msg(0x204, col=2, keys=2); msg(0x205)
            assert clipboard_text(hwnd) == 'LINK', clipboard_text(hwnd)
            assert len(launched()) == before
            assert not re.search(rb'\x1b\[<(?!35;)', data()), data()
            evidence['shift_copy'] = 'LINK'
            menu(4)
            wait_for(lambda: clipboard_text(hwnd) == uri)
            def copy_selected():
                msg(0x204, keys=2); msg(0x205)
                u.SendMessageW(hwnd, 0, 0, 0)
            elapsed = clipboard_contention(copy_selected, .05)
            assert clipboard_text(hwnd) == 'LINK', (clipboard_text(hwnd), current())
            assert .025 <= elapsed < .25, elapsed
            evidence['clipboard_transient_lock_seconds'] = elapsed
            evidence['copy_address_preserves_selection'] = True
            menu(4)
            wait_for(lambda: clipboard_text(hwnd) == uri)
            elapsed = clipboard_contention(copy_selected, .4)
            assert .07 <= elapsed < .3 and clipboard_text(hwnd) == uri, elapsed
            copy_selected()
            assert clipboard_text(hwnd) == 'LINK', clipboard_text(hwnd)
            evidence['clipboard_lock_timeout_seconds'] = elapsed
            menu(4)
            wait_for(lambda: clipboard_text(hwnd) == uri)
            menu(1, clipboard_hold=.4)  # Copy and Paste must use the label.
            received = bytes.fromhex(wait_snapshot(current, lambda v:
                b'LINK' in bytes.fromhex(v.get('hex', '')))['hex'])
            assert uri.encode() not in received and clipboard_text(hwnd) == uri, received
            evidence['copy_paste_uses_selection_when_clipboard_busy'] = True

            phase('ctrl-drag', scene+'\x1b[?1002;1006h')
            before = len(launched())
            msg(0x201, col=1, keys=9); msg(0x200, col=4, keys=9); msg(0x202, col=4, keys=8)
            msg(0x204, keys=2); msg(0x205)
            assert clipboard_text(hwnd) == 'LINK', clipboard_text(hwnd)
            assert len(launched()) == before and b'\x1b[<' not in data(), data()
            evidence['ctrl_drag_copy'] = 'LINK'

            phase('shift-takeover', scene+'\x1b[?1002;1006h')
            before = len(launched())
            msg(0x201, col=1, keys=9)
            u.SendMessageW(hwnd, 0x100, 0x10, 1)  # Shift becomes local selection
            msg(0x200, col=4, keys=5); msg(0x202, col=4, keys=4)
            u.SendMessageW(hwnd, 0x101, 0x10, 0xc0000001)
            msg(0x204, keys=2); msg(0x205)
            assert clipboard_text(hwnd) == 'LINK', clipboard_text(hwnd)
            assert len(launched()) == before and b'\x1b[<' not in data(), data()
            evidence['shift_takeover'] = True

            phase('mixed-buttons', scene+'\x1b[?1002;1006h')
            before = len(launched())
            msg(0x201, keys=9)
            msg(0x20b, keys=(1 << 16) | 41)  # X1 while link press is held
            msg(0x200, col=4, keys=41)
            msg(0x20c, col=4, keys=(1 << 16) | 9)
            msg(0x202, col=4, keys=8)
            reports = re.findall(rb'\x1b\[<(\d+);(\d+);(\d+)([Mm])', data())
            assert reports == [(b'144', b'3', b'2', b'M'), (b'176', b'5', b'2', b'M'),
                               (b'144', b'5', b'2', b'm')], reports
            assert len(launched()) == before and gui_state(hwnd).capture != hwnd
            evidence['mixed_buttons'] = data().hex()

            phase('cancel-capture', scene+'\x1b[?1003;1006h')
            before = len(launched())
            msg(0x201, keys=9)
            assert gui_state(hwnd).capture == hwnd
            u.SendMessageW(hwnd, 0x1f, 0, 0)  # WM_CANCELMODE
            assert gui_state(hwnd).capture != hwnd
            msg(0x202, keys=8); msg(0x200, col=3)
            assert len(launched()) == before
            assert b'\x1b[<35;4;2M' in data() and not re.search(rb'\x1b\[<(?!35;)', data()), data()
            evidence['capture_cancel'] = data().hex()

            phase('cancel-resize', scene+'\x1b[?1002;1006h')
            before = len(launched())
            u.GetWindowRect(hwnd, c.byref(outer))
            msg(0x201, keys=9)
            assert u.MoveWindow(hwnd, outer.left, outer.top,
                                outer.right-outer.left+2*cw, outer.bottom-outer.top, True)
            msg(0x202, keys=8)
            assert len(launched()) == before and b'\x1b[<' not in data(), data()
            assert u.MoveWindow(hwnd, outer.left, outer.top,
                                outer.right-outer.left, outer.bottom-outer.top, True)
            evidence['resize_cancel'] = True

            phase('before-frozen', scene)
            u.SendMessageW(hwnd, 0x2a3, 0, 0)
            phase('frozen', '\x1b[?2026h\x1b[2;2H'+link(other, 'LINK')+'\x1b[?2026$p')
            assert b'\x1b[?2026;1$y' in data(), data()
            previous = {str(p) for p in launches.glob('*.json')}
            msg(0x201, keys=9); msg(0x202, keys=8)
            new = wait_for(lambda: [p for p in launches.glob('*.json') if str(p) not in previous])
            assert read_snapshot(new[0]).get('argv') == [uri], read_snapshot(new[0])
            phase('unfrozen', '\x1b[?2026l')
            previous = {str(p) for p in launches.glob('*.json')}
            msg(0x201, keys=9); msg(0x202, keys=8)
            new = wait_for(lambda: [p for p in launches.glob('*.json') if str(p) not in previous])
            assert read_snapshot(new[0]).get('argv') == [other], read_snapshot(new[0])
            evidence['synchronized_clicks'] = [uri, other]

            foreign = 'file://nemoterm-remote.invalid/C:/sample.txt'
            phase('remote-file', '\x1b[2;2H'+link(foreign, 'LINK'))
            tip, text = hover(foreign)
            assert 'Remote file link' in text, text
            menu(4, can_open=False)
            wait_for(lambda: clipboard_text(hwnd) == foreign)
            evidence['remote_file_copy_only'] = foreign

            # Keep an old main-screen link while alternate-screen output
            # forces registry eviction, then verify that it cannot alias any
            # new target. Long URI/history and image budgets share the process.
            burst = scene + '\x1b[?1049h' + ''.join(
                link(f'{scheme}://host/{i:05d}/'+1950*'x', f'line {i:05d}')+'\r\n'
                for i in range(6000)) + '\x1b[?1049l'
            solid = '\x1bP0;1q"1;1;32;32#1;2;100;0;0'+5*'!32~-'+'!32B-\x1b\\'
            burst += 800*('\x1b[7;4H'+solid)
            phase('budget-eviction', burst, timeout=20)
            before = len(launched())
            msg(0x200); msg(0x201, keys=9); msg(0x202, keys=8)
            time.sleep(.12)
            assert len(launched()) == before and tooltip(process.pid) is None
            evidence['budget_eviction'] = dict(uris=6000, images=800, old_link_inactive=True)
            evidence.update(peak_private_ws=max(s['private_ws'] for s in samples),
                            peak_total_ws=max(s['total_ws'] for s in samples),
                            peak_private_commit=max(s['private_commit'] for s in samples),
                            executable_sha256=hashlib.sha256((root/'dist/nemoterm.exe').read_bytes()).hexdigest())
            assert evidence['peak_private_ws'] < 20_000_000, evidence
            (root/'research/hyperlink-window-observed.json').write_text(json.dumps(evidence, indent=2))
            print('Native hyperlink checks passed:', evidence)
        finally:
            try:
                if clipboard: clipboard.restore()
            finally:
                stop.set(); worker.join(2); k.CloseHandle(handle)
                write_snapshot(control, {'stop': True})
                if hwnd:
                    u.PostMessageW(hwnd, 0x100, 0x1b, 1)  # close any test popup
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    if hwnd: u.PostMessageW(hwnd, 0x10, 0, 0)
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.terminate(); process.wait(timeout=5)
                    raise
