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
from console_process_utils import owned_processes, creation_time, workload_process_role

exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
shells = json.loads(subprocess.check_output([str(exe),'--no-tabs', '--list-shells'], timeout=10))
required = set(filter(None, os.environ.get('NEMOTERM_REQUIRED_SHELLS', '').split(',')))
available = {shell['id'] for shell in shells if shell['available']}
assert required <= available, dict(missing=sorted(required-available), detected=shells)
profile = 'shell-test-' + uuid.uuid4().hex
keypath = 'Software\\Nemo\\Nemoterm\\Sessions\\' + profile
with winreg.CreateKey(winreg.HKEY_CURRENT_USER, keypath) as key:
    winreg.SetValueEx(key, 'WarnOnClose', 0, winreg.REG_DWORD, 0)
observed = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                detected=shells, launches={}, process_lifetime=[],
                process_observer=os.environ.get('NEMOTERM_SHELL_PROCESS_OBSERVER', '1') != '0')
tracked_processes = {}
started_at = time.monotonic()


def record_processes(phase, sid=None, root_pid=None, discover=False):
    """Retain identities across parent exit; diagnostics never stop a process."""
    if not observed['process_observer']:
        return
    event = dict(phase=phase, shell=sid, seconds=round(time.monotonic()-started_at, 6),
                 windows_filetime=time.time_ns()//100+116444736000000000)
    try:
        if discover:
            for row in owned_processes(root_pid, exited=[]):
                handle = k.OpenProcess(0x101000, False, row['pid'])
                if not handle:
                    continue
                identity = (row['pid'], creation_time(handle))
                if identity in tracked_processes:
                    k.CloseHandle(handle)
                    continue
                tracked_processes[identity] = (handle, dict(
                    pid=row['pid'], parent=row['parent'], path=row['path'],
                    created=identity[1], shell=sid, root_pid=root_pid,
                    role=workload_process_role(row, root_pid, str(exe))))
        event['processes'] = []
        for handle, identity in tracked_processes.values():
            code = w.DWORD()
            queried = bool(k.GetExitCodeProcess(handle, c.byref(code)))
            event['processes'].append(dict(identity,
                signaled=k.WaitForSingleObject(handle, 0) == 0,
                exit_code=code.value if queried else None))
    except Exception as error:
        event['diagnostic_error'] = repr(error)
    observed['process_lifetime'].append(event)

def send(hwnd, text):
    for bytepair in range(0, len(encoded := text.encode('utf-16-le')), 2):
        u.SendMessageW(hwnd, 0x102, int.from_bytes(encoded[bytepair:bytepair+2], 'little'), 1)

def shell_path(path, sid):
    value = path.as_posix()
    if sid == 'wsl-bash': return '/mnt/' + value[0].lower() + value[2:]
    if sid == 'git-bash': return '/' + value[0].lower() + value[2:]
    return value

def directory_command(marker, sid):
    path = shell_path(marker, sid)
    ready = marker.with_suffix('.done')
    done_path = shell_path(ready, sid)
    # Redirection creates the output before the command writes it. Publish a
    # separate completion marker only after that file has been written/closed.
    # Waiting for marker.exists alone can read an empty or partial directory.
    if sid in ('pwsh', 'powershell'):
        command = "[IO.File]::WriteAllText('"+path.replace("'", "''")+"',(Get-Location).ProviderPath)"
        command += "; [IO.File]::WriteAllText('"+done_path.replace("'", "''")+"','done')"
    elif sid == 'cmd':
        # CMD redirects builtins using its ANSI encoding unless /U is set.
        command = 'cmd /d /u /c cd >"'+str(marker)+'" & type nul >"'+str(ready)+'"'
    else:
        command = ("pwd -W > " if sid == "git-bash" else "pwd > ")+shlex.quote(path)
        command += '; : > '+shlex.quote(done_path)
    return command, ready


def same_directory(actual, expected, sid):
    if sid == 'wsl-bash':
        # This fixture uses a Windows directory mounted in WSL. Compare its
        # Windows file identity, including short/long names and junctions.
        assert actual.startswith('/mnt/') and len(actual) > 7 and actual[6] == '/', actual
        actual = actual[5] + ':' + actual[6:]
    return os.path.samefile(actual, expected)

def wsl_terminfo_roundtrip(hwnd, folder, evidence):
    # Run inside the selected WSL shell. Neither the fixture nor tput sets
    # TERM for the first row. The second row is scoped to one child process.
    script = folder/'terminfo.sh'
    script.write_bytes(r"""set -eu
cd -- "$(dirname -- "$0")"
exec >terminfo.log 2>&1
old=$(stty -g </dev/tty)
trap 'stty "$old" </dev/tty; : >terminfo.done' EXIT
stty -echo -icanon min 1 time 0 </dev/tty
printf 'inherited=%s\n' "${TERM-}"
for which in inherited xterm; do
  (
    if [ "$which" = xterm ]; then export TERM=xterm; row=5; col=8; else row=2; col=3; fi
    printf '%s-colors=' "$which"; tput colors
    # tput coordinates start at zero. The actual terminal must reply with
    # one-based coordinates. Capturing tput output alone would not prove this.
    tput cup "$row" "$col" >/dev/tty
    printf '\033[6n' >/dev/tty
    reply=''; IFS= read -r -t 5 -d R reply </dev/tty
    printf '%s-reply=' "$which"; printf '%sR' "$reply" | od -An -tx1 | tr -d ' \n'; printf '\n'
  )
done
printf 'complete=yes\n'
""".encode('ascii'))
    send(hwnd, 'bash '+shlex.quote(shell_path(script, 'wsl-bash'))+'\r')
    log = folder/'terminfo.log'
    try:
        wait_for((folder/'terminfo.done').exists, timeout=20)
    finally:
        evidence['log'] = log.read_text(encoding='utf-8', errors='replace') if log.exists() else None
    rows = dict(line.split('=', 1) for line in (evidence['log'] or '').splitlines() if '=' in line)
    assert rows.get('inherited') == 'xterm-256color' and rows.get('inherited-colors') == '256', rows
    assert rows.get('inherited-reply') == b'\x1b[3;4R'.hex() and rows.get('xterm-reply') == b'\x1b[6;9R'.hex(), rows
    assert rows.get('complete') == 'yes', rows


def terminal_windows():
    result = {}
    @c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def visit(hwnd, _):
        name, pid = c.create_unicode_buffer(128), w.DWORD()
        u.GetClassNameW(hwnd, name, len(name))
        if name.value == 'Nemoterm' and u.IsWindowVisible(hwnd):
            u.GetWindowThreadProcessId(hwnd, c.byref(pid)); result[hwnd] = pid.value
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
            command, ready_file = directory_command(marker, sid)
            process = subprocess.Popen([str(exe),*(['--automation'] if sid == 'wsl-bash' else []),'--no-tabs', '-load', profile, '--shell', sid,
                '--directory', str(starting)],
                env=dict(os.environ, NEMOTERM_CONPTY='bundled'),
                creationflags=subprocess.CREATE_NO_WINDOW)
            handle = k.OpenProcess(0x410, False, process.pid)
            try:
                hwnd = wait_for(lambda: find_window(process.pid), timeout=15)
                time.sleep(.7)
                send(hwnd, command + '\r')
                try:
                    wait_for(ready_file.exists, timeout=30)
                except Exception:
                    print('Owned shell terminal exit:', process.poll(), flush=True)
                    if process.poll() is None:
                        capture(hwnd, root/'build'/('shell-failed-' + sid + '.png'))
                    raise
                actual = marker.read_text(encoding='utf-16-le' if sid == 'cmd' else 'utf-8-sig').strip()
                expected = starting.as_posix() if sid == 'git-bash' else shell_path(starting, sid)
                assert same_directory(actual, starting, sid), (sid, actual, expected)
                observed['launches'][sid] = dict(command_executed=True,
                    memory=memory_sample(handle), path=shell['path'], directory=actual)
                record_processes('command-completed', sid, process.pid, discover=True)
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
                        new = [(pid, window) for window, pid in terminal_windows().items()
                               if window not in before and pid == process.pid]
                        return new[0] if len(new) == 1 else None
                    duplicate_pid, duplicate_hwnd = wait_for(duplicated, timeout=15)
                    assert duplicate_pid == process.pid
                    try:
                        duplicate_marker = Path(temporary)/(sid+'-duplicate.txt')
                        time.sleep(.7)
                        duplicate_command, duplicate_ready = directory_command(duplicate_marker, sid)
                        send(duplicate_hwnd, duplicate_command+'\r')
                        wait_for(duplicate_ready.exists, timeout=30)
                        actual_duplicate = duplicate_marker.read_text(encoding='utf-8-sig').strip()
                        expected_duplicate = destination.as_posix() if sid == 'git-bash' else posix_directory
                        assert same_directory(actual_duplicate, destination, sid), (sid, actual_duplicate, expected_duplicate)
                        observed['launches'][sid]['duplicate_directory'] = actual_duplicate
                        record_processes('duplicate-before-close', sid, process.pid, discover=True)
                    finally:
                        observed['launches'][sid]['duplicate_close_filetime'] = time.time_ns()//100+116444736000000000
                        u.PostMessageW(duplicate_hwnd, 0x10, 0, 0)
                        wait_for(lambda: not u.IsWindow(duplicate_hwnd), timeout=10)
                        assert process.poll() is None
                        record_processes('duplicate-window-closed', sid, process.pid)
                if sid == 'wsl-bash':
                    wsl_terminfo_roundtrip(hwnd, Path(temporary),
                        observed['launches'][sid].setdefault('terminfo', {}))
                    from wsl_pager_interaction import exercise
                    exercise(process, hwnd, Path(temporary), shell_path, send,
                             observed['launches'][sid].setdefault('less', {}), root/'research')
                print('Shell launch passed:', sid, flush=True)
                send(hwnd, 'exit\r')
                process.wait(timeout=10)
                assert process.returncode == 0, (sid, process.returncode)
                record_processes('frontend-exited', sid, process.pid)
            finally:
                k.CloseHandle(handle)
                if process.poll() is None:
                    hwnd = find_window(process.pid)
                    if hwnd: send(hwnd, 'exit\r')
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired: process.terminate(); process.wait(timeout=5)
    if distro := os.environ.get('NEMOTERM_TEST_WSL_DISTRO'):
        assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
        assert 'wsl-bash' in observed['launches']
        # Every terminal and shell above has already exited. WSL 1 retains its
        # Linux init processes in the controller's Job until the disposable
        # distribution is stopped; these are fixture infrastructure, not tabs.
        linux = subprocess.check_output(['wsl.exe','--distribution',distro,'--exec','ps','-eo','pid,ppid,comm'],
            timeout=15, creationflags=subprocess.CREATE_NO_WINDOW).decode('utf-8-sig')
        assert not any(line.split()[-1] in ('bash','ash') for line in linux.splitlines() if line.split()), linux
        subprocess.run(['wsl.exe','--terminate',distro], check=True, timeout=30,
                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        observed['wsl_fixture_teardown'] = dict(distribution=distro, shells_exited=True, linux_processes=linux)
finally:
    record_processes('fixture-finished')
    try:
        (root/'research/shell-window-observed.json').write_text(json.dumps(observed, indent=2), encoding='utf-8')
    finally:
        for handle, _ in tracked_processes.values():
            k.CloseHandle(handle)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, keypath)
