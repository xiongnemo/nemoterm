"""Actual Codex TUI + loopback text fixture in an owned Nemoterm window.

No online model, global input or existing Codex session is used. This proves
specific real-client rendering/input paths, not long-term live-service use.
"""
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    tempfile, Path, time, wait_for, find_window, capture, memory_sample)
from clipboard_test_utils import SavedClipboard, clipboard_text
from console_process_utils import owned_processes
from codex_fixture_server import FixtureServer, COPY_TEXT, PASTE_TEXT
import argparse
import shutil
import threading
import unicodedata
import uuid
import winreg

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--codex', default=shutil.which('codex.exe'))
parser.add_argument('--inline', action='store_true', help='Also test Codex --no-alt-screen')
parser.add_argument('--input-text', default='NEMOTERM_INPUT 中文 e\u0301 \U0001f642')
parser.add_argument('--trace-input', action='store_true', help='Trace owned Codex console reads for diagnosis')
parser.add_argument('--diagnose-surrogates', action='store_true', help='Diagnostic mutation only; suppress surrogate release text in Codex reads')
parser.add_argument('--font', default='SarasaTermSC Nerd Font Light')
args = parser.parse_args()
assert args.codex, 'Provide --codex with an installed native Codex executable'
codex = Path(args.codex).resolve()
exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
mode = 'inline' if args.inline else 'default'
evidence = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    codex_launcher=str(codex), codex_launcher_sha256=hashlib.sha256(codex.read_bytes()).hexdigest(),
    codex_version=subprocess.check_output([str(codex), '--version'], text=True, timeout=15).strip(),
    mode=mode, font=args.font, backend='loopback deterministic SSE; no model or tool calls', checks=[], screenshots=[])
profile = 'codex-window-'+uuid.uuid4().hex
keypath = 'Software\\Nemo\\Nemoterm\\Sessions\\'+profile
with winreg.CreateKey(winreg.HKEY_CURRENT_USER, keypath) as key:
    winreg.SetValueEx(key, 'WarnOnClose', 0, winreg.REG_DWORD, 0)


def key(vk, scan):
    lp = 1 | ((scan & 255) << 16) | ((scan & 256) << 16)
    u.SendMessageW(hwnd, 0x100, vk, lp)
    u.SendMessageW(hwnd, 0x101, vk, lp | 0xc0000000)


def type_text(text):
    for char in text:
        u.SendMessageW(hwnd, 0x109, ord(char), 0)


def set_clipboard(text):
    raw = (text+'\0').encode('utf-16-le')
    allocation = k.GlobalAlloc(2, len(raw))
    assert allocation
    ptr = k.GlobalLock(allocation)
    assert ptr
    c.memmove(ptr, raw, len(raw)); k.GlobalUnlock(allocation)
    try:
        wait_for(lambda: u.OpenClipboard(hwnd))
        try:
            assert u.EmptyClipboard()
            assert u.SetClipboardData(13, allocation)
            allocation = None
        finally:
            u.CloseClipboard()
    finally:
        if allocation: k.GlobalFree(allocation)


def all_text():
    previous = u.GetClipboardSequenceNumber()
    u.SendMessageW(hwnd, 0x111, 0x0170, 0)
    wait_for(lambda: u.GetClipboardSequenceNumber() != previous)
    return clipboard_text(hwnd)


def frame(name):
    # Selection updates invalidate a frame asynchronously; capture the paint
    # after the native message handler has returned, not its preceding frame.
    time.sleep(.1)
    filename = f'codex-{mode}-{name}.png'
    evidence['screenshots'].append(dict(file=filename, pixel_sha256=capture(hwnd, filename)))


def geometry():
    r = w.RECT(); assert u.GetClientRect(hwnd, c.byref(r))
    cols, rows = (r.right-2)//cell_w, (r.bottom-2)//cell_h
    return cols, rows, (r.right-cols*cell_w)//2, (r.bottom-rows*cell_h)//2


def select(x, y, end):
    _, _, left, top = geometry()
    start = (top+y*cell_h+cell_h//2) << 16 | (left+x*cell_w+cell_w//2)
    finish = (top+y*cell_h+cell_h//2) << 16 | (left+end*cell_w+cell_w//2)
    u.SendMessageW(hwnd, 0x201, 5, start)
    u.SendMessageW(hwnd, 0x200, 5, finish)
    u.SendMessageW(hwnd, 0x202, 4, finish)
    return start


def find_marker():
    cols, rows, _, _ = geometry()
    visible = []
    for row in range(rows):
        point = select(0, row, cols-1)
        previous = u.GetClipboardSequenceNumber()
        u.SendMessageW(hwnd, 0x204, 2, point)
        u.SendMessageW(hwnd, 0x205, 0, point)
        wait_for(lambda: u.GetClipboardSequenceNumber() != previous)
        text = clipboard_text(hwnd) or ''
        visible.append(text)
        if COPY_TEXT in text:
            prefix = text[:text.index(COPY_TEXT)]
            width = lambda s: sum(0 if unicodedata.combining(ch) else
                                  2 if unicodedata.east_asian_width(ch) in ('W','F') else 1 for ch in s)
            select(width(prefix), row, width(prefix+COPY_TEXT)-1)
            return row
    raise AssertionError(('Marker absent from visible grid', visible))


try:
    (root/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='codex-window-', dir=root/'build') as temporary, FixtureServer() as server:
        folder = Path(temporary).resolve()
        assert (root/'build').resolve() in folder.parents
        home, work = folder/'codex-home', folder/'work'
        home.mkdir(); work.mkdir()
        config = '''model = "nemoterm-ui-fixture"
model_provider = "nemoterm_fixture"
check_for_update_on_startup = false
sandbox_mode = "read-only"
approval_policy = "never"
[model_providers.nemoterm_fixture]
name = "Nemoterm local UI fixture"
base_url = "http://127.0.0.1:PORT/v1"
wire_api = "responses"
requires_openai_auth = false
[analytics]
enabled = false
[feedback]
enabled = false
'''.replace(':PORT/', f':{server.server_port}/')
        config += '\n[projects.'+json.dumps(str(work))+']\ntrust_level = "trusted"\n'
        (home/'config.toml').write_text(config)
        env = {name: value for name, value in os.environ.items() if name.upper() in {
            'SYSTEMROOT','WINDIR','COMSPEC','PATH','PATHEXT','TEMP','TMP','USERPROFILE',
            'APPDATA','LOCALAPPDATA','PROGRAMDATA','PROGRAMFILES','PROGRAMFILES(X86)',
            'NUMBER_OF_PROCESSORS','PROCESSOR_ARCHITECTURE'}}
        env.update(CODEX_HOME=str(home), NEMOTERM_CONPTY='bundled', TERM='xterm-256color')
        process = subprocess.Popen([str(exe), '-load', profile, '--cols', '100', '--rows', '30',
            '--font', args.font, '-e', str(codex), '--no-daemon',
            '--cd', str(work), *(['--no-alt-screen'] if args.inline else [])],
            cwd=work, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
        saved = session = script = sampler = input_session = input_script = None
        input_trace = []
        handles = {}; samples = []; sample_errors = []; stop = threading.Event()
        hwnd = None
        try:
            hwnd = wait_for(lambda: find_window(process.pid), timeout=15)
            saved = SavedClipboard(hwnd)
            wait_for(lambda: 'Ask Codex to do anything' in all_text(), timeout=20)
            evidence['checks'].append('actual-client-startup')
            evidence['startup_processes'] = owned_processes(process.pid)
            for p in evidence['startup_processes']:
                handle = k.OpenProcess(0x100410, False, p['pid'])
                assert handle
                handles[p['pid']] = handle
                if Path(p['path']).name.lower() == 'codex.exe':
                    p['sha256'] = hashlib.sha256(Path(p['path']).read_bytes()).hexdigest()
            r = w.RECT(); u.GetClientRect(hwnd, c.byref(r))
            cell_w, cell_h = (r.right-2)//100, (r.bottom-2)//30
            initial = w.RECT(); u.GetWindowRect(hwnd, c.byref(initial))
            frame('startup')
            if args.trace_input or args.diagnose_surrogates:
                import frida
                agent_pid = next(p['pid'] for p in evidence['startup_processes']
                                 if Path(p['path']).name.lower() == 'codex.exe')
                input_session = frida.attach(agent_pid)
                probe = (root/'tests/codex_console_probe.js').read_text()
                if args.diagnose_surrogates:
                    probe = probe.replace('const suppress = false;', 'const suppress = true;')
                    evidence['diagnostic_mutation'] = 'Suppress surrogate key-up characters at Codex ReadConsoleInputW boundary; not a product fix'
                input_script = input_session.create_script(probe)
                input_script.on('message', lambda message, data: input_trace.append(message))
                input_script.load()

            def sample():
                while not stop.is_set():
                    try:
                        samples.append(dict(time=time.monotonic(), **memory_sample(handles[process.pid])))
                    except Exception as exc:
                        sample_errors.append(repr(exc)); break
                    stop.wait(.1)
            sampler = threading.Thread(target=sample, daemon=True); sampler.start()
            prompt = args.input_text
            type_text(prompt)
            time.sleep(.5)
            evidence['typed_text'] = all_text()
            key(13, 28)
            wait_for(lambda: server.preview_ready.is_set() or server.errors, timeout=25)
            assert not server.errors, server.errors
            preview = wait_for(lambda: (text if 'print("中文与 Unicode")' in (text := all_text()) else None), timeout=10)
            evidence['markdown_preview'] = preview
            frame('markdown')
            server.preview_release.set()
            wait_for(lambda: server.completed or server.errors, timeout=25)
            assert not server.errors, server.errors
            first = next(request for request in server.requests if not request['auxiliary'] and request['turn']==1)
            assert prompt in first['user_text'], server.requests
            wait_for(lambda: 'NEMOTERM_REPLY_1_DONE' in all_text(), timeout=20)
            time.sleep(.5)
            frame('response')
            evidence['checks'].extend(['unicode-input-reaches-real-client', 'streamed-markdown-long-reply'])
            print(f'{mode}: real Codex rendered streamed response', flush=True)
            sizes = [(700,480),(1000,700),(650,450),
                     (initial.right-initial.left, initial.bottom-initial.top)]
            for cycle in range(8):
                for width, height in sizes:
                    assert u.MoveWindow(hwnd, 30, 30, width, height, True)
                    time.sleep(.12)
                    assert process.poll() is None
            wait_for(lambda: 'NEMOTERM_REPLY_1_DONE' in all_text(), timeout=10)
            evidence['checks'].append('32-live-client-resizes')
            frame('resized')
            stop.set(); sampler.join(timeout=3)
            assert not sample_errors, sample_errors
            evidence['uninstrumented_frontend'] = dict(samples=len(samples),
                **{'peak_'+key: max(item[key] for item in samples)
                   for key in ('private_ws','total_ws','private_commit')})
            assert evidence['uninstrumented_frontend']['peak_private_ws'] < 20_000_000
            evidence['post_resize_processes'] = owned_processes(process.pid)

            # Only this phase is instrumented. It is excluded from memory peaks.
            import frida
            session = frida.attach(process.pid)
            script = session.create_script((root/'tests/agent_key_probe.js').read_text())
            key_errors = []
            script.on('message', lambda message, data: key_errors.append(message) if message.get('type') == 'error' else None)
            script.load(); serial = 0
            assert not key_errors, key_errors
            def chord(vk, scan, modifiers):
                global serial
                serial += 1
                script.exports_sync.key(dict(id=serial, key=vk, scan=scan, modifiers=modifiers))
                assert u.PostMessageW(hwnd, 0x8322, 0, 0)
                answer = wait_for(lambda: script.exports_sync.result())
                assert not key_errors, key_errors
                assert answer == {'id':serial}, answer
            row = find_marker()
            evidence['selected_row'] = row
            frame('selection')
            set_clipboard('COPY sentinel')
            chord(67,46,[16,17,160,162])
            try:
                wait_for(lambda: clipboard_text(hwnd) == COPY_TEXT)
            except AssertionError:
                evidence['actual_copied_text'] = clipboard_text(hwnd)
                raise
            evidence['checks'].append('shift-grid-select-ctrl-shift-c-exact-unicode')
            set_clipboard(PASTE_TEXT)
            chord(86,47,[16,17,160,162])
            time.sleep(.2); key(13,28)
            wait_for(lambda: len(server.completed) == 2 or server.errors, timeout=20)
            assert not server.errors, server.errors
            submitted = [request for request in server.requests if not request['auxiliary']]
            assert PASTE_TEXT in submitted[1]['user_text'], submitted[1]
            wait_for(lambda: 'NEMOTERM_REPLY_2_DONE' in all_text(), timeout=10)
            evidence['checks'].append('ctrl-shift-v-exact-unicode-through-real-client')
            frame('paste')
            evidence['requests'] = server.requests
            evidence['copy_text'] = COPY_TEXT
            evidence['input_scope'] = 'own-HWND Unicode and mouse messages; own UI-thread keyboard state; not physical devices'
        except Exception as exc:
            evidence['error'] = repr(exc)
            evidence['server_errors'] = server.errors
            evidence['requests'] = server.requests
            if hwnd and process.poll() is None:
                frame('failure')
                evidence['failure_text'] = all_text()
            (root/f'build/codex-{mode}-failure.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
            raise
        finally:
            stop.set()
            if sampler: sampler.join(timeout=3)
            if script: script.unload()
            if session: session.detach()
            if input_script: input_script.unload()
            if input_session: input_session.detach()
            if args.trace_input or args.diagnose_surrogates:
                (root/f'build/codex-{mode}-input-trace.json').write_text(json.dumps(input_trace, indent=2))
            if saved: saved.restore()
            if hwnd and process.poll() is None: u.PostMessageW(hwnd, 0x10, 0, 0)
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.terminate(); process.wait(timeout=5)
            cleanup = []
            for pid, handle in handles.items():
                code = w.DWORD()
                try:
                    wait_for(lambda: k.GetExitCodeProcess(handle, c.byref(code)) and code.value != 259, timeout=8)
                    cleanup.append(dict(pid=pid, exit_code=code.value))
                finally: k.CloseHandle(handle)
            evidence['cleanup'] = cleanup
        output = root/f'build/codex-{mode}-diagnostic.json' if args.diagnose_surrogates else root/f'research/codex-{mode}-observed.json'
        output.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print('Diagnostic-only' if args.diagnose_surrogates else 'Real Codex window checks passed:', json.dumps(evidence['checks']),
              json.dumps(evidence['uninstrumented_frontend']), flush=True)
finally:
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, keypath)
