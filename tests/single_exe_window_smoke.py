"""One copied executable, same-image console host, delegated shell lifetime."""
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, time, wait_for, find_window)
from console_process_utils import owned_processes
import shutil
import uuid
import winreg

source = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'build/single-exe-dist/nemoterm.exe')).resolve()
evidence = dict(executable_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
profile = 'single-exe-test-' + uuid.uuid4().hex
keypath = 'Software\\Nemo\\Nemoterm\\Sessions\\' + profile
with winreg.CreateKey(winreg.HKEY_CURRENT_USER, keypath) as key:
    winreg.SetValueEx(key, 'WarnOnClose', 0, winreg.REG_DWORD, 0)
try:
    with tempfile.TemporaryDirectory(prefix='nemoterm single 中 ') as directory:
        directory = Path(directory)
        isolated = directory/'portable'; isolated.mkdir()
        exe = isolated/'nemoterm.exe'; shutil.copyfile(source, exe)
        licenses = subprocess.check_output([str(exe), '--licenses'], timeout=10).decode('utf-8')
        assert 'Microsoft Corporation' in licenses and 'Simon Tatham' in licenses and 'MIT License' in licenses
        assert 'The Open Group' in licenses and 'Digital Equipment Corporation' in licenses
        evidence['embedded_licenses_bytes'] = len(licenses.encode('utf-8'))
        report, stop = directory/'report.json', directory/'stop'
        process = subprocess.Popen([str(exe), '-load', profile, '-e', sys.executable,
            str(root/'tests/delegated_console_fixture.py'), str(report), str(stop)],
            env=dict(os.environ, NEMOTERM_CONPTY='bundled'), creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            hwnd = wait_for(lambda: find_window(process.pid))
            wait_for(report.exists)
            child = json.loads(report.read_text())
            time.sleep(.2)
            assert process.poll() is None and find_window(process.pid) == hwnd
            launcher = k.OpenProcess(0x1000, False, child['launcher'])
            if launcher:
                try:
                    code = w.DWORD(); assert k.GetExitCodeProcess(launcher, c.byref(code))
                    assert code.value == 0, code.value
                finally: k.CloseHandle(launcher)
            processes = owned_processes(process.pid)
            hosts = [p for p in processes if p['pid'] != process.pid and
                     os.path.normcase(p['path']) == os.path.normcase(str(exe))]
            assert len(hosts) == 1, processes
            assert all(Path(p['path']).name.lower() not in ('openconsole.exe', 'conhost.exe') for p in processes)
            evidence.update(processes=processes, host_same_image=True,
                            launcher_exit_preserves_console=True)
            stop.touch()
            process.wait(timeout=10)
            assert process.returncode == 0
            assert sorted(p.name for p in isolated.iterdir()) == ['nemoterm.exe']
            evidence['only_executable_in_directory'] = True
        finally:
            if process.poll() is None:
                stop.touch()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    u.PostMessageW(hwnd, 0x10, 0, 0)
                    try: process.wait(timeout=3)
                    except subprocess.TimeoutExpired: process.terminate(); process.wait()
    (root/'research/single-exe-observed.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print('Single executable isolation, same-image host and delegated console lifetime passed')
finally:
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, keypath)
