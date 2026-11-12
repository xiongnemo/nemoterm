"""Keep a delegated child alive after its initial console launcher exits."""
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, time, wait_for, find_window)
from console_process_utils import owned_processes
import uuid
import winreg

exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
profile = 'delegate-test-' + uuid.uuid4().hex
keypath = 'Software\\Nemo\\Nemoterm\\Sessions\\' + profile
with winreg.CreateKey(winreg.HKEY_CURRENT_USER, keypath) as key:
    winreg.SetValueEx(key, 'WarnOnClose', 0, winreg.REG_DWORD, 0)
evidence = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest())
try:
    with tempfile.TemporaryDirectory(prefix='nemoterm-delegate-') as directory:
        report, stop = Path(directory)/'report.json', Path(directory)/'stop'
        p = subprocess.Popen([str(exe), '-load', profile, '-e', sys.executable,
            str(root/'tests/delegated_console_fixture.py'), str(report), str(stop)],
            env=dict(os.environ, NEMOTERM_CONPTY='bundled'), creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            hwnd = wait_for(lambda: find_window(p.pid))
            wait_for(report.exists)
            fixture = json.loads(report.read_text())
            launcher = k.OpenProcess(0x1000, False, fixture['launcher'])
            if launcher:
                try:
                    code = w.DWORD(); assert k.GetExitCodeProcess(launcher, c.byref(code))
                    assert code.value == 0, code.value
                finally: k.CloseHandle(launcher)
            assert p.poll() is None and find_window(p.pid) == hwnd
            evidence.update(fixture=fixture, processes=owned_processes(p.pid), launcher_exit_preserves_child=True)
            stop.touch(); p.wait(timeout=10)
            assert p.returncode == 0
            evidence['last_client_exit_closes_terminal'] = True
        finally:
            if p.poll() is None:
                stop.touch()
                try: p.wait(timeout=3)
                except subprocess.TimeoutExpired: p.terminate(); p.wait()
    (root/'research/delegated-console-observed.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print('Delegated console lifetime and last-client shutdown passed')
finally:
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, keypath)
