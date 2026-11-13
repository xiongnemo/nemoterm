"""Windows PowerShell selected through a pwsh-inherited terminal environment.

Only owned windows receive input. Explicit/custom commands must retain their
deliberate module path; the built-in Windows PowerShell profile rebuilds it.
"""
from native_test_utils import (root, c, w, u, hashlib, json, os, subprocess,
    sys, tempfile, Path, time, wait_for, find_window)
from owned_job import OwnedJob
import uuid
import winreg

exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
digest = hashlib.sha256(exe.read_bytes()).hexdigest()
shells = {s['id']: s for s in json.loads(subprocess.check_output(
    [str(exe), '--list-shells'], timeout=10))}
assert shells['powershell']['available'] and shells['pwsh']['available'], \
    'This regression requires installed Windows PowerShell and pwsh'
core = Path(subprocess.check_output([shells['pwsh']['path'], '-NoProfile',
    '-Command', '$PSHOME'], timeout=10).decode('utf-8-sig').strip())/'Modules'
desktop = Path(shells['powershell']['path']).parent/'Modules'
assert core.is_dir() and desktop.is_dir()
evidence = dict(executable_sha256=digest, completed=False, checks=[])
profile = 'powershell-env-' + uuid.uuid4().hex
keypath = 'Software\\Nemo\\Nemoterm\\Sessions\\' + profile


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def send(hwnd, text):
    encoded = text.encode('utf-16-le')
    for offset in range(0, len(encoded), 2):
        u.SendMessageW(hwnd, 0x102,
            int.from_bytes(encoded[offset:offset+2], 'little'), 1)


with winreg.CreateKey(winreg.HKEY_CURRENT_USER, keypath) as key:
    for name, value in dict(WarnOnClose=0, CloseOnExit=1, NemoChooseShell=0).items():
        winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
    winreg.SetValueEx(key, 'NemoShell', 0, winreg.REG_SZ, 'powershell')
try:
    with tempfile.TemporaryDirectory(prefix='nemo-module-env-') as directory:
        directory = Path(directory)
        custom = directory/'custom modules 中'
        custom.mkdir()
        inherited = ';'.join(map(str, (core, custom, desktop)))
        child_env = dict(os.environ, PSModulePath=inherited,
            NEMOTERM_CONPTY='bundled', NEMOTERM_ENV_TEST_SENTINEL='kept')
        powershell = shells['powershell']['path']
        cases = (
            ('selected', ['--shell', 'powershell'], True, True),
            ('saved-tabs', ['--tabs'], True, True),
            ('custom', ['--shell-command',
                subprocess.list2cmdline([powershell, '-NoLogo', '-NoProfile'])], False, False),
            ('explicit', ['-e', powershell, '-NoLogo', '-NoProfile'], False, False),
            ('pwsh', ['--shell', 'pwsh'], False, True),
        )
        for name, arguments, clean, available in cases:
            report, done = directory/(name+'.txt'), directory/(name+'.done')
            # The reporter only uses built-in syntax and .NET for its files, so
            # it can still describe a broken Utility module in the control cases.
            command = "$f=Get-Command Get-FileHash -ErrorAction SilentlyContinue;"
            command += "$h=if($f){(Get-FileHash -LiteralPath " + literal(exe)
            command += " -Algorithm SHA256).Hash}else{''};"
            command += "[IO.File]::WriteAllLines(" + literal(report)
            command += ",[string[]]@([string][bool]$f,$env:PSModulePath,$h,$env:NEMOTERM_ENV_TEST_SENTINEL));"
            command += "[IO.File]::WriteAllText(" + literal(done) + ",'done')"
            with OwnedJob() as job:
                process = job.spawn([str(exe), '-load', profile, '--cols', '100',
                    '--rows', '24', *arguments], env=child_env,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                hwnd = wait_for(lambda: find_window(process.pid), timeout=15)
                time.sleep(.8)
                send(hwnd, command+'\r')
                wait_for(done.exists, timeout=30)
                rows = report.read_text(encoding='utf-8-sig').splitlines()
                assert len(rows) == 4, (name, rows)
                found = rows[0] == 'True'
                record = dict(name=name, rebuilt_path=clean,
                    get_file_hash_available=found, module_path=rows[1],
                    file_hash=rows[2].lower(), sentinel=rows[3])
                evidence['checks'].append(record)
                assert found == available, record
                assert rows[3] == 'kept', record
                if clean:
                    assert str(core).lower() not in rows[1].lower(), record
                    assert str(custom).lower() not in rows[1].lower(), record
                else:
                    assert str(core).lower() in rows[1].lower(), record
                    assert str(custom).lower() in rows[1].lower(), record
                if available:
                    assert rows[2].lower() == digest, record
                send(hwnd, 'exit\r')
                process.wait(timeout=10)
                assert process.returncode == 0, (name, process.returncode)
                print('PowerShell environment passed:', name, flush=True)
        evidence['completed'] = True
finally:
    if sys.exc_info()[0]: evidence['error'] = repr(sys.exc_info()[1])
    (root/'research/powershell-environment-observed.json').write_text(
        json.dumps(evidence, indent=2), encoding='utf-8')
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, keypath)
