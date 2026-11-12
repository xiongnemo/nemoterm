"""Compare title-stack replies and actual HWND titles with independent XTerm."""
import argparse
import re
import uuid
import winreg
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, wait_for, read_snapshot, write_snapshot, wait_snapshot,
    find_window, memory_sample)
from owned_job import OwnedJob

u.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, c.c_int]
exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
parser = argparse.ArgumentParser()
parser.add_argument('--modes', action='store_true')
args = parser.parse_args()
reference = json.loads((root/('tests/title_modes_reference.json' if args.modes else
    'tests/title_stack_reference.json')).read_text(encoding='utf-8'))
evidence = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    reference_run=reference['source_run'], checks={})
evidence['runtime_files'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
    for p in (exe.parent/'OpenConsole.exe', exe.parent/'conpty.dll') if p.exists()}
profile = 'titles-'+uuid.uuid4().hex
keypath = 'Software\\Nemo\\Nemoterm\\Sessions\\'+profile
samples = []
try:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, keypath) as key:
        winreg.SetValueEx(key, 'WarnOnClose', 0, winreg.REG_DWORD, 0)
        winreg.SetValueEx(key, 'RemoteQTitleAction', 0, winreg.REG_DWORD, 2)
        winreg.SetValueEx(key, 'NemoRenderer', 0, winreg.REG_DWORD, 0)
    with tempfile.TemporaryDirectory(prefix='nemoterm-titles-') as tmp, OwnedJob() as job:
        report, control = Path(tmp)/'report', Path(tmp)/'control'
        process = job.spawn([str(exe), '-load', profile, '--cols', '80', '--rows', '24',
            '-e', sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control)],
            env=dict(os.environ, NEMOTERM_CONPTY='bundled', NEMOTERM_TEST_UTF8_INPUT='1',
                     NEMOTERM_TEST_EXACT_OUTPUT='1'),
            creationflags=subprocess.CREATE_NO_WINDOW)
        handle = k.OpenProcess(0x410, False, process.pid)
        try:
            hwnd = wait_for(lambda: find_window(process.pid))
            wait_for(lambda: read_snapshot(report))
            def title():
                value = c.create_unicode_buffer(8192)
                u.GetWindowTextW(hwnd, value, len(value))
                return value.value
            def phase(name, sequence, reply, native_title):
                write_snapshot(control, dict(phase=name, sequence=sequence+'\x1b[5n'))
                value = wait_snapshot(lambda: read_snapshot(report), lambda v:
                    v.get('phase') == name and bytes.fromhex(v.get('hex', '')).endswith(b'\x1b[0n'))
                raw = bytes.fromhex(value['hex'])
                assert raw == reply.encode()+b'\x1b[0n', (name, raw, reply)
                if native_title is not None:
                    wait_for(lambda: title() == native_title)
                samples.append(memory_sample(handle))
                evidence['checks'][name] = dict(reply=value['hex'], native_title=title())
            for name, case in reference['cases'].items():
                final_title = case['native_title'] if args.modes else \
                    re.findall('\x1b\\]l(.*?)\x1b\\\\', case['reply'])[-1]
                phase(name, case['sequence'], case['reply'], final_title)
            # Repeated saves must retain only the most recent ten strings.
            large = 'BOUNDED-'+'x'*980
            churn = ''.join(f'\x1b]0;{large}{i}\x07\x1b[22t' for i in range(1000))
            final_title = large+'990'
            phase('bounded-churn', '\x1b[>0;1;2;3T'+churn+'\x1b[23t'*1000+'\x1b[20t\x1b[21t',
                  '\x1b]L'+final_title+'\x1b\\\x1b]l'+final_title+'\x1b\\', final_title)
            for metric in ('private_ws', 'total_ws', 'private_commit'):
                evidence['peak_'+metric] = max(s[metric] for s in samples)
            assert evidence['peak_private_ws'] < 20_000_000, evidence['peak_private_ws']
            write_snapshot(control, dict(stop=True))
            assert process.wait(timeout=10) == 0
        finally:
            job.finish(grace=0)
            process.wait(timeout=5)
            k.CloseHandle(handle)
finally:
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, keypath)
    filename = 'title-modes-window-observed.json' if args.modes else 'titles-window-observed.json'
    (root/'research'/filename).write_text(json.dumps(evidence, indent=2), encoding='utf-8')
print('Native title modes' if args.modes else 'Native title stacks', 'passed:', len(evidence['checks']), 'checks;',
      evidence['peak_private_ws'], 'bytes peak private WS')
