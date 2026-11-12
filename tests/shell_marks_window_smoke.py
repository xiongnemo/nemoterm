"""Owned-window shell marks through ConPTY, native menus and saved bindings.

Run on GitHub-hosted Windows while local interactive testing is paused.
"""
from native_test_utils import *
from clipboard_test_utils import SavedClipboard, clipboard_text
import frida
import uuid
import winreg

u.GetSystemMenu.argtypes, u.GetSystemMenu.restype = [w.HWND, w.BOOL], w.HMENU
u.GetSubMenu.argtypes, u.GetSubMenu.restype = [w.HMENU, c.c_int], w.HMENU
u.GetMenuItemCount.argtypes, u.GetMenuItemCount.restype = [w.HMENU], c.c_int
u.GetMenuItemID.argtypes, u.GetMenuItemID.restype = [w.HMENU, c.c_int], w.UINT
u.GetMenuState.argtypes, u.GetMenuState.restype = [w.HMENU, w.UINT, w.UINT], w.UINT
u.GetMenuStringW.argtypes = [w.HMENU, w.UINT, w.LPWSTR, c.c_int, w.UINT]

exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
profile = 'shell-marks-test-' + uuid.uuid4().hex
keypath = 'Software\\Nemo\\Nemoterm\\Sessions\\' + profile
observed = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), checks=[], samples=[])
with winreg.CreateKey(winreg.HKEY_CURRENT_USER, keypath) as key:
    for name, value in dict(WarnOnClose=0, NemoPreviousPromptBinding=0x726,
                            NemoNextPromptBinding=0x728, NemoSelectCommandBinding=0x743,
                            NemoSelectOutputBinding=0x74f, ScrollbackLines=100).items():
        winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)

try:
    with tempfile.TemporaryDirectory(prefix='nemoterm-shell-marks-') as tmp:
        report, control = (Path(tmp)/n for n in ('report', 'control'))
        process = subprocess.Popen([str(exe), '-load', profile, '--cols', '80', '--rows', '24', '-e',
            sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control)],
            env=dict(os.environ, NEMOTERM_CONPTY='bundled', NEMOTERM_TEST_UTF8_INPUT='1'),
            creationflags=subprocess.CREATE_NO_WINDOW)
        saved = session = script = handle = sampler = None
        stop = threading.Event()
        try:
            hwnd = wait_for(lambda: find_window(process.pid))
            wait_for(lambda: read_snapshot(report))
            saved = SavedClipboard(hwnd)
            handle = k.OpenProcess(0x410, False, process.pid)
            assert handle
            def sample():
                while not stop.is_set():
                    observed['samples'].append(memory_sample(handle))
                    stop.wait(0.025)
            sampler = threading.Thread(target=sample)
            sampler.start()
            session = frida.attach(process.pid)
            script = session.create_script((root/'tests/agent_key_probe.js').read_text())
            script.load(); script.exports_sync.isolate_mouse(hex(hwnd)); serial = 0

            def action(key, scan, modifiers=(16, 17, 18, 160, 162, 164)):
                global serial
                serial += 1
                script.exports_sync.key(dict(id=serial, key=key, scan=scan, modifiers=list(modifiers)))
                assert u.PostMessageW(hwnd, 0x8322, 0, 0)
                assert wait_for(lambda: script.exports_sync.result()) == dict(id=serial)

            def phase(name, sequence):
                write_snapshot(control, dict(phase=name, sequence=sequence+'\x1b[5n'))
                wait_snapshot(lambda: read_snapshot(report),
                    lambda v: v.get('phase') == name and v.get('hex') == '1b5b306e')
                observed['samples'].append(memory_sample(handle))

            def copy_selected(expected, name):
                before = u.GetClipboardSequenceNumber()
                action(67, 46, (16, 17, 160, 162))
                wait_for(lambda: u.GetClipboardSequenceNumber() != before)
                actual = clipboard_text(hwnd)
                assert actual == expected, (name, actual, expected)
                observed['checks'].append(dict(name=name, text=actual))

            def menu(command, expected, name):
                u.SendMessageW(hwnd, 0x111, command, 0)
                copy_selected(expected, name)

            def find_menu(parent, command):
                for index in range(u.GetMenuItemCount(parent)):
                    if u.GetMenuItemID(parent, index) == command:
                        return parent
                    child = u.GetSubMenu(parent, index)
                    found = find_menu(child, command) if child else None
                    if found: return found
                return None

            def menu_state(command):
                parent = find_menu(u.GetSystemMenu(hwnd, False), command)
                assert parent
                u.SendMessageW(hwnd, 0x117, parent, 0)  # update owned submenu without opening it
                text = c.create_unicode_buffer(160)
                assert u.GetMenuStringW(parent, command, text, len(text), 0)
                return dict(label=text.value, disabled=bool(u.GetMenuState(parent, command, 0) & 3))

            command1, output1 = 'echo 中 e\u0301', 'ONE 中 e\u0301'
            command2, output2 = 'printf two', 'TWO 👋'
            phase('protocols', '\x1b[?25l\x1b[2J\x1b[H'
                '\x1b]133;A\a> \x1b]133;B\x1b\\'+command1+'\x1b]133;C\a'+output1+'\x1b]133;D;0\a\r\n'
                '\x1b]633;A\a> \x1b]633;B\a'+command2+'\x1b]633;E;different\\x3bmetadata;untrusted\a'
                '\x1b]633;C\a'+output2+'\x1b]633;D;17\x1b\\\r\n\x1b]133;A\a> ')
            menu(0x920, command2, 'latest command uses cells, not metadata')
            menu(0x930, output2, '633 output and supplementary Unicode')
            # Selection targets the second command. Previous Prompt moves to the first.
            action(0x26, 0x48)
            action(67, 46)
            copy_selected(command1, 'saved previous-prompt and select-command bindings')
            action(79, 24)
            copy_selected(output1, 'saved select-output binding and combining Unicode')
            action(0x28, 0x50)
            menu(0x930, output2, 'saved next-prompt binding')
            assert read_snapshot(report)['hex'] == '1b5b306e', read_snapshot(report)

            # Resize the owned window only. Reflow must preserve the selected record.
            wr, cr = w.RECT(), w.RECT()
            u.GetWindowRect(hwnd, c.byref(wr)); u.GetClientRect(hwnd, c.byref(cr))
            cw, ch = (cr.right-2)//80, (cr.bottom-2)//24
            frame_x, frame_y = wr.right-wr.left-cr.right, wr.bottom-wr.top-cr.bottom
            for cols in (20, 100, 32, 80):
                assert u.MoveWindow(hwnd, wr.left, wr.top, cols*cw+2+frame_x,
                                    24*ch+2+frame_y, True)
                wait_snapshot(lambda: read_snapshot(report), lambda v: v.get('columns') == cols)
                menu(0x920, command2, f'command after resize to {cols}')
                menu(0x930, output2, f'output after resize to {cols}')
            capture(hwnd, 'shell-marks-selected.png')

            phase('alternate', '\x1b[?1049h\x1b]133;A\aBAD\x1b]133;B\ax\x1b]133;C\ay\x1b]133;D;1\a')
            assert menu_state(0x930)['disabled'], menu_state(0x930)
            u.SendMessageW(hwnd, 0x111, 0x930, 0)
            copy_selected(output2, 'alternate screen cannot replace main command selection')
            phase('back', '\x1b[?1049l')
            assert not menu_state(0x930)['disabled'], menu_state(0x930)
            menu(0x930, output2, 'main output retained across alternate screen')

            phase('bookmark', '\x1b[5;1H\x1b]1337;SetMark\a\r\nAFTER')
            # Scroll resets the selected navigation record, then previous visits SetMark.
            u.SendMessageW(hwnd, 0x115, 7, 0)  # WM_VSCROLL / SB_BOTTOM
            u.SendMessageW(hwnd, 0x111, 0x900, 0)
            u.SendMessageW(hwnd, 0x111, 0x930, 0)
            copy_selected(output2, 'SetMark is a bookmark without an invented output range')
            u.SendMessageW(hwnd, 0x111, 0x900, 0)  # unfinished prompt
            u.SendMessageW(hwnd, 0x111, 0x900, 0)  # second command
            menu(0x920, command2, '1337 bookmark navigation reaches prior command')

            phase('bounded-churn', ''.join(
                '\x1b]633;A\a\x1b]633;B\ac\x1b]633;E;'+('x'*4096)+
                '\a\x1b]633;C\ao\x1b]633;D;0\a\r\n' for _ in range(1000)))
            menu(0x930, 'o', 'latest output after bounded metadata churn')

            phase('clipped-history', '\x1bc\x1b[3J\x1b[2J\x1b[H'
                '\x1b]133;A\a>\x1b]133;B\ac\x1b]133;C\a'+
                ('\r\nline'*150)+'\x1b]133;D;0\a')
            state = menu_state(0x930)
            assert not state['disabled'] and '(Truncated)' in state['label'], state
            assert menu_state(0x920)['disabled'], menu_state(0x920)
            menu(0x930, '\r\n'.join(['line']*124), 'output clipped to 100 history plus 24 screen rows')
            observed['truncated_menu'] = state
            capture(hwnd, 'shell-marks-truncated.png')
            observed['samples'].append(memory_sample(handle))
            observed['private_ws_sampled_peak'] = max(s['private_ws'] for s in observed['samples'])
            assert observed['private_ws_sampled_peak'] < 20_000_000, observed['samples']
            assert read_snapshot(report)['hex'] == '1b5b306e', read_snapshot(report)
        finally:
            stop.set()
            if sampler: sampler.join(timeout=2)
            observed['last_snapshot'] = read_snapshot(report)
            if script: script.unload()
            if session: session.detach()
            if saved: saved.restore()
            if handle: k.CloseHandle(handle)
            write_snapshot(control, dict(stop=True))
            try: process.wait(timeout=8)
            except subprocess.TimeoutExpired: process.terminate(); process.wait(timeout=5)
finally:
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, keypath)
    (root/'research/shell-marks-observed.json').write_text(json.dumps(observed, indent=2), encoding='utf-8')
print('Shell mark protocols, native actions, Unicode copy, reflow and memory passed')
