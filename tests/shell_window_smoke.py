"""Launch every detected shell in owned windows and execute a marker command.

No global input or clipboard changes. A temporary saved profile prevents a
close-confirmation dialog; the user's Default Settings are not changed.
"""
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    tempfile, Path, time, wait_for, find_window, memory_sample, capture)
import shlex
import uuid
import winreg
import urllib.parse

exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
shells = json.loads(subprocess.check_output([str(exe), '--list-shells'], timeout=10))
profile = 'shell-test-' + uuid.uuid4().hex
keypath = 'Software\\Nemo\\Nemoterm\\Sessions\\' + profile
with winreg.CreateKey(winreg.HKEY_CURRENT_USER, keypath) as key:
    winreg.SetValueEx(key, 'WarnOnClose', 0, winreg.REG_DWORD, 0)
observed = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                detected=shells, launches={})

def send(hwnd, text):
    for bytepair in range(0, len(encoded := text.encode('utf-16-le')), 2):
        u.SendMessageW(hwnd, 0x102, int.from_bytes(encoded[bytepair:bytepair+2], 'little'), 1)

def shell_path(path, sid):
    value = path.as_posix()
    if sid == 'wsl-bash': return '/mnt/' + value[0].lower() + value[2:]
    if sid == 'git-bash': return '/' + value[0].lower() + value[2:]
    return value

def same_directory(actual, expected, sid):
    if sid == 'wsl-bash':
        # This fixture uses a Windows directory mounted in WSL. Compare its
        # Windows file identity, including short/long names and junctions.
        assert actual.startswith('/mnt/') and len(actual) > 7 and actual[6] == '/', actual
        actual = actual[5] + ':' + actual[6:]
    return os.path.samefile(actual, expected)

def terminal_windows():
    result = {}
    @c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def visit(hwnd, _):
        name, pid = c.create_unicode_buffer(128), w.DWORD()
        u.GetClassNameW(hwnd, name, len(name))
        if name.value == 'Nemoterm' and u.IsWindowVisible(hwnd):
            u.GetWindowThreadProcessId(hwnd, c.byref(pid)); result[pid.value] = hwnd
        return True
    u.EnumWindows(visit, 0)
    return result

def title_contains(hwnd, marker):
    text = c.create_unicode_buffer(512); u.GetWindowTextW(hwnd, text, len(text))
    return marker in text.value

try:
    with tempfile.TemporaryDirectory(prefix='nemoterm-shells-') as temporary:
        starting = Path(temporary)/'startup 中 space'
        starting.mkdir()
        for shell in shells:
            if not shell['available']:
                continue
            sid = shell['id']
            if os.environ.get('NEMOTERM_TEST_SHELL') not in (None, sid):
                continue
            marker = Path(temporary) / (sid + '.txt')
            path = shell_path(marker, sid)
            if sid in ('pwsh', 'powershell'):
                command = "[IO.File]::WriteAllText('"+path.replace("'", "''")+"',(Get-Location).ProviderPath)"
            elif sid == 'cmd':
                command = 'chcp 65001>nul & cd >"' + str(marker) + '"'
            else:
                command = ("pwd -W > " if sid == "git-bash" else "pwd > ") + shlex.quote(path)
            process = subprocess.Popen([str(exe), '-load', profile, '--shell', sid,
                '--directory', str(starting)],
                env=dict(os.environ, NEMOTERM_CONPTY='bundled'),
                creationflags=subprocess.CREATE_NO_WINDOW)
            handle = k.OpenProcess(0x410, False, process.pid)
            try:
                hwnd = wait_for(lambda: find_window(process.pid), timeout=15)
                time.sleep(.7)
                send(hwnd, command + '\r')
                try:
                    wait_for(marker.exists, timeout=30)
                except Exception:
                    print('Owned shell terminal exit:', process.poll(), flush=True)
                    if process.poll() is None:
                        capture(hwnd, root/'build'/('shell-failed-' + sid + '.png'))
                    raise
                actual = marker.read_text(encoding='utf-8-sig').strip()
                expected = starting.as_posix() if sid == 'git-bash' else shell_path(starting, sid)
                assert same_directory(actual, starting, sid), (sid, actual, expected)
                observed['launches'][sid] = dict(command_executed=True,
                    memory=memory_sample(handle), path=shell['path'], directory=actual)
                if sid in ('git-bash', 'wsl-bash'):
                    destination = Path(temporary)/('duplicate 中;$(literal) '+sid)
                    destination.mkdir()
                    posix_directory = ('/tmp/' + destination.relative_to(Path(tempfile.gettempdir())).as_posix()
                                       if sid == 'git-bash' else shell_path(destination, sid))
                    ready = 'cwd-ready-' + uuid.uuid4().hex
                    sequence = '\x1b]7;file://localhost' + urllib.parse.quote(posix_directory, safe='/') + '\a'
                    sequence += '\x1b]2;' + ready + '\a'
                    escaped_sequence = sequence.replace('\x1b', r'\033').replace('\a', r'\007')
                    send(hwnd, "printf %b " + shlex.quote(escaped_sequence) + '; sleep 1\r')
                    wait_for(lambda: title_contains(hwnd, ready))
                    before = set(terminal_windows())
                    u.SendMessageW(hwnd, 0x111, 0x30, 0)
                    def duplicated():
                        new = [(pid, window) for pid, window in terminal_windows().items() if pid not in before]
                        return new[0] if len(new) == 1 else None
                    duplicate_pid, duplicate_hwnd = wait_for(duplicated, timeout=15)
                    duplicate_handle = k.OpenProcess(0x100000, False, duplicate_pid)
                    assert duplicate_handle
                    k.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
                    try:
                        duplicate_marker = Path(temporary)/(sid+'-duplicate.txt')
                        time.sleep(.7)
                        send(duplicate_hwnd, ('pwd -W > ' if sid == 'git-bash' else 'pwd > ')+shlex.quote(shell_path(duplicate_marker, sid))+'\r')
                        wait_for(duplicate_marker.exists, timeout=30)
                        actual_duplicate = duplicate_marker.read_text(encoding='utf-8-sig').strip()
                        expected_duplicate = destination.as_posix() if sid == 'git-bash' else posix_directory
                        assert same_directory(actual_duplicate, destination, sid), (sid, actual_duplicate, expected_duplicate)
                        observed['launches'][sid]['duplicate_directory'] = actual_duplicate
                    finally:
                        u.PostMessageW(duplicate_hwnd, 0x10, 0, 0)
                        assert k.WaitForSingleObject(duplicate_handle, 10000) == 0
                        k.CloseHandle(duplicate_handle)
                print('Shell launch passed:', sid, flush=True)
                send(hwnd, 'exit\r')
                process.wait(timeout=10)
                assert process.returncode == 0, (sid, process.returncode)
            finally:
                k.CloseHandle(handle)
                if process.poll() is None:
                    hwnd = find_window(process.pid)
                    if hwnd: send(hwnd, 'exit\r')
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired: process.terminate(); process.wait(timeout=5)
    (root/'research/shell-window-observed.json').write_text(json.dumps(observed, indent=2), encoding='utf-8')
finally:
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, keypath)
