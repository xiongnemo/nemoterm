"""Exercise only a newly spawned Nemoterm window; never sends global input.

SendMessage invokes the real Win32 handler, and a child records bytes after the
bundled ConPTY round trip. This is distinct from physical-device automation.
"""
import ctypes as c
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from fixture_io import read_snapshot, write_snapshot, wait_snapshot

root = Path(__file__).resolve().parent.parent
u = c.windll.user32
u.SetProcessDPIAware()
u.SendMessageTimeoutW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM,
                                 w.UINT, w.UINT, c.POINTER(c.c_size_t)]
u.ClientToScreen.argtypes = [w.HWND, c.POINTER(w.POINT)]
u.MoveWindow.argtypes = [w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.BOOL]
u.ShowWindow.argtypes = [w.HWND, c.c_int]

class GuiThreadInfo(c.Structure):
    _fields_ = [('cbSize', w.DWORD), ('flags', w.DWORD),
                ('hwndActive', w.HWND), ('hwndFocus', w.HWND),
                ('hwndCapture', w.HWND), ('hwndMenuOwner', w.HWND),
                ('hwndMoveSize', w.HWND), ('hwndCaret', w.HWND),
                ('rcCaret', w.RECT)]

u.GetGUIThreadInfo.argtypes = [w.DWORD, c.POINTER(GuiThreadInfo)]
u.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]

def capture_owner(hwnd):
    info = GuiThreadInfo(cbSize=c.sizeof(GuiThreadInfo))
    tid = u.GetWindowThreadProcessId(hwnd, None)
    if not u.GetGUIThreadInfo(tid, c.byref(info)):
        raise c.WinError()
    return info.hwndCapture
def wait_for(fn, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError('Timed out waiting for test condition')

def windows(pid):
    matches = []
    @c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def visit(hwnd, _):
        owner, cls = w.DWORD(), c.create_unicode_buffer(128)
        u.GetWindowThreadProcessId(hwnd, c.byref(owner))
        u.GetClassNameW(hwnd, cls, 128)
        if owner.value == pid and cls.value == 'Nemoterm' and u.IsWindowVisible(hwnd):
            matches.append(hwnd)
        return True
    u.EnumWindows(visit, 0)
    return matches[0] if len(matches) == 1 else None

with tempfile.TemporaryDirectory(prefix='nemoterm-mouse-') as directory:
    directory = Path(directory)
    report, control = directory/'report.json', directory/'control.json'
    env = dict(os.environ, NEMOTERM_CONPTY='bundled')
    process = subprocess.Popen([str(root/'dist/nemoterm.exe'), '--cols', '80',
        '--rows', '24', '-e', sys.executable, str(root/'tests/mouse_fixture.py'),
        str(report), str(control)], env=env, creationflags=subprocess.CREATE_NO_WINDOW)
    def request(value):
        write_snapshot(control, value)
    def snapshot():
        value = read_snapshot(report)
        if value.get('error'):
            raise AssertionError(value['error'])
        if process.poll() is not None:
            raise AssertionError(f'Fixture exited early ({process.returncode}): {value}')
        return value
    evidence = []
    try:
        hwnd = wait_for(lambda: windows(process.pid))
        wait_for(snapshot)
        rect = w.RECT()
        u.GetClientRect(hwnd, c.byref(rect))
        cell_width = (rect.right - rect.left - 2) // 80
        def msg(message, wp=0, x=20, y=20):
            result = c.c_size_t()
            if not u.SendMessageTimeoutW(hwnd, message, wp,
                    (x & 0xffff) | ((y & 0xffff) << 16), 2, 2000, c.byref(result)):
                raise c.WinError()
            return result.value
        def phase(name, sequence):
            request({'phase': name, 'sequence': sequence})
            wait_for(lambda: snapshot().get('phase') == name)
            time.sleep(0.15)  # output must reach the terminal before input
        def recorded():
            time.sleep(0.25)
            value = wait_snapshot(snapshot, lambda value: 'hex' in value)
            evidence.append(value)
            return bytes.fromhex(value['hex'])
        phase('sgr-drag', '\x1b[?1002;1006h')
        msg(0x201, 1)  # left down
        msg(0x200, 1, 20+cell_width, 20)  # drag one cell
        msg(0x202, 0, 20+cell_width, 20)
        data = recorded()
        matches = re.findall(rb'\x1b\[<(\d+);(\d+);(\d+)([Mm])', data)
        assert len(matches) == 3, data
        assert [int(m[0]) for m in matches] == [0, 32, 0], data
        assert [m[3] for m in matches] == [b'M', b'M', b'm'], data
        assert int(matches[1][1]) == int(matches[0][1])+1, data
        phase('side-button-drag', '\x1b[?1002;1006h')
        for button, mask in [(1, 0x20), (2, 0x40)]:
            assert msg(0x20b, (button << 16) | mask | 8) == 1
            msg(0x200, mask | 8, 20+cell_width, 20)
            assert msg(0x20c, (button << 16) | 8,
                       20+cell_width, 20) == 1
        data = recorded()
        matches = re.findall(rb'\x1b\[<(\d+);(\d+);(\d+)([Mm])', data)
        assert [int(m[0]) for m in matches] == [144, 176, 144, 145, 177, 145], data
        assert [m[3] for m in matches] == [b'M', b'M', b'm'] * 2, data
        phase('mixed-buttons-capture', '\x1b[?1002;1006h')
        msg(0x201, 1)
        assert capture_owner(hwnd) == hwnd, 'left down lost capture'
        msg(0x20b, (1 << 16) | 0x21)
        assert capture_owner(hwnd) == hwnd, 'side down lost capture'
        msg(0x202, 0x20)  # releasing left must retain side-button capture
        assert capture_owner(hwnd) == hwnd, 'left up lost side-button capture'
        msg(0x200, 0x20, 20+cell_width, 20)
        msg(0x1f)  # cancellation synthesizes exactly one side-button release
        msg(0x20c, 1 << 16)
        data = recorded()
        matches = re.findall(rb'\x1b\[<(\d+);\d+;\d+([Mm])', data)
        assert matches == [(b'0', b'M'), (b'128', b'M'), (b'0', b'm'),
                           (b'160', b'M'), (b'128', b'm')], data
        phase('side-button-shift', '\x1b[?1002;1006h')
        msg(0x20b, (2 << 16) | 0x44)
        msg(0x200, 0x44, 20+cell_width, 20)
        msg(0x20c, (2 << 16) | 4, 20+cell_width, 20)
        assert recorded() == b''
        phase('pixel-motion', '\x1b[?1003;1016h')
        msg(0x200, 0, 22, 20)
        msg(0x200, 0, 23, 20)
        data = recorded()
        matches = re.findall(rb'\x1b\[<35;(\d+);(\d+)M', data)
        assert len(matches) >= 2 and int(matches[-1][0]) == int(matches[-2][0])+1, data
        phase('capture-cancel', '\x1b[?1002;1006h')
        msg(0x201, 1)
        msg(0x1f)  # WM_CANCELMODE
        msg(0x202)
        data = recorded()
        assert re.fullmatch(rb'\x1b\[<0;(\d+);(\d+)M\x1b\[<0;\1;\2m', data), data
        phase('shift-selection', 'ABCDE\x1b[?1002;1006h')
        msg(0x201, 1|4)
        msg(0x200, 1|4, 60, 20)
        msg(0x202, 0, 60, 20)
        assert recorded() == b''
        phase('four-direction-wheels', '\x1b[?1002;1006h')
        point = w.POINT(20, 20)
        assert u.ClientToScreen(hwnd, c.byref(point))
        for message, delta in [(0x20a, 120), (0x20a, -120),
                               (0x20e, 120), (0x20e, -120)]:
            msg(message, ((delta & 0xffff) << 16), point.x, point.y)
        data = recorded()
        matches = re.findall(rb'\x1b\[<(\d+);\d+;\d+M', data)
        assert matches == [b'64', b'65', b'67', b'66'], data
        phase('independent-wheel-accumulators', '\x1b[?1002;1006h')
        msg(0x20a, 60 << 16, point.x, point.y)
        msg(0x20e, 60 << 16, point.x, point.y)
        assert recorded() == b''
        msg(0x20a, 60 << 16, point.x, point.y)
        msg(0x20e, 60 << 16, point.x, point.y)
        data = recorded()
        matches = re.findall(rb'\x1b\[<(\d+);\d+;\d+M', data)
        assert matches == [b'64', b'67'], data
        msg(0x08)  # WM_KILLFOCUS, before enabling reporting
        phase('focus-handler-roundtrip', '\x1b[?1004h')
        msg(0x07)  # WM_SETFOCUS
        msg(0x07)
        msg(0x08)
        msg(0x08)
        data = recorded()
        # The real foreground-window check can reconcile injected WM_*FOCUS
        # messages back to OS focus between handlers. Every resulting state
        # transition must still survive ConPTY, without duplicate notifications.
        events = re.findall(rb'\x1b\[([IO])', data)
        assert re.fullmatch(rb'(?:\x1b\[[IO])+', data), data
        assert set(events) == {b'I', b'O'}, data
        assert all(a != b for a, b in zip(events, events[1:])), data
        phase('osc-dynamic-colour-roundtrip',
              '\x1b]10;rgb:12/34/56\x07\x1b]10;?\x1b\\')
        data = recorded()
        assert data == b'\x1b]10;rgb:1212/3434/5656\x1b\\', data
        phase('osc-palette-roundtrip',
              '\x1b]4;5;rgb:ab/cd/ef\x07\x1b]4;5;?\x07')
        data = recorded()
        assert data == b'\x1b]4;5;rgb:abab/cdcd/efef\x07', data
        phase('resize', '')
        u.MoveWindow(hwnd, 50, 50, 900, 600, True)
        bigger = wait_snapshot(snapshot, lambda value: value.get('columns', 0) > 80)
        u.MoveWindow(hwnd, 50, 50, 500, 300, True)
        smaller = wait_snapshot(snapshot, lambda value: value.get('columns', 80) < 80)
        evidence.extend([bigger, smaller])
        phase('rapid-resize', '')
        for index in range(25):
            width, height = (900, 600) if index % 2 == 0 else (500, 300)
            assert u.MoveWindow(hwnd, 50, 50, width, height, True)
        settled = wait_snapshot(snapshot, lambda value:
            (value.get('columns'), value.get('rows')) == (bigger['columns'], bigger['rows']))
        evidence.append(settled)
        phase('maximize-restore', '')
        u.ShowWindow(hwnd, 3)  # SW_MAXIMIZE on this test's window only
        maximized = wait_snapshot(snapshot, lambda value:
            value.get('columns', 0) > bigger['columns'] and value.get('rows', 0) > bigger['rows'])
        u.ShowWindow(hwnd, 9)  # SW_RESTORE
        restored = wait_snapshot(snapshot, lambda value:
            (value.get('columns'), value.get('rows')) == (bigger['columns'], bigger['rows']))
        evidence.extend([maximized, restored])
        target = root/'research/mouse-window-observed.json'
        target.write_text(json.dumps({'test_pid': process.pid, 'observations': evidence}, indent=2))
        print(f'Native mouse/ConPTY/resize smoke passed: {target}')
    finally:
        request({'stop': True})
        process.wait(timeout=10)
