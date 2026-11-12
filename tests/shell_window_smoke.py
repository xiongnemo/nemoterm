"""Launch every detected shell in owned windows and execute a marker command.

No global input or clipboard changes. A temporary saved profile prevents a
close-confirmation dialog; the user's Default Settings are not changed.
"""
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    tempfile, Path, time, wait_for, find_window, memory_sample, capture)
import shlex
import uuid
import winreg

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

try:
    with tempfile.TemporaryDirectory(prefix='nemoterm-shells-') as temporary:
        for shell in shells:
            if not shell['available']:
                continue
            sid = shell['id']
            if os.environ.get('NEMOTERM_TEST_SHELL') not in (None, sid):
                continue
            marker = Path(temporary) / (sid + '.txt')
            path = marker.as_posix()
            if sid in ('pwsh', 'powershell'):
                command = "[IO.File]::WriteAllText('"+path.replace("'", "''")+"','NEMOTERM_SHELL_OK')"
            elif sid == 'cmd':
                command = 'echo NEMOTERM_SHELL_OK>"' + str(marker) + '"'
            else:
                if sid == 'wsl-bash':
                    path = '/mnt/' + path[0].lower() + path[2:]
                elif sid == 'git-bash':
                    path = '/' + path[0].lower() + path[2:]
                command = "printf NEMOTERM_SHELL_OK > " + shlex.quote(path)
            process = subprocess.Popen([str(exe), '-load', profile, '--shell', sid],
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
                assert marker.read_text().strip() == 'NEMOTERM_SHELL_OK', sid
                observed['launches'][sid] = dict(command_executed=True,
                    memory=memory_sample(handle), path=shell['path'])
                print('Shell launch passed:', sid, flush=True)
                send(hwnd, 'exit\r')
                process.wait(timeout=10)
                assert process.returncode == 0, (sid, process.returncode)
            finally:
                k.CloseHandle(handle)
                if process.poll() is None:
                    hwnd = find_window(process.pid)
                    if hwnd: u.PostMessageW(hwnd, 0x10, 0, 0)
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired: process.terminate(); process.wait(timeout=5)
    (root/'research/shell-window-observed.json').write_text(json.dumps(observed, indent=2), encoding='utf-8')
finally:
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, keypath)
