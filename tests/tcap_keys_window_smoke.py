"""Replay independent terminfo keys through the owned UI thread and ConPTY."""
from native_test_utils import (root, w, u, hashlib, json, os, subprocess, sys,
    tempfile, Path, read_snapshot, write_snapshot, wait_for, find_window)
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile
import frida

if os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
    raise RuntimeError('Native terminfo replay requires a GitHub-hosted runner')

exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
reference_path = Path(__file__).with_name('tcap_key_reference.json')
reference = json.loads(reference_path.read_text())
assert reference['count'] == 1378
marker = b'\x1b[0n'
identity = b'\x1bP1+r544e=787465726D2D323536636F6C6F72;'
evidence = dict(completed=False, executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    reference_sha256=hashlib.sha256(reference_path.read_bytes()).hexdigest(),
    physical_input=False, clipboard_access=False, thread_keyboard_state_restored=True,
    cases={}, excluded={}, profiles={}, mismatches={}, identity_policy=reference['identity_policy'])
profile = dict(ShiftedArrowKeys=2, WarnOnClose=0, NemoRenderer=0, NemoTabs=0,
    CtrlShiftIns='none', AltF4=0, AltSpace=0, FullScreenOnAltEnter=0, CtrlAltKeys=1,
    ComposeKey=0, NemoWin32Input=0, LinuxFunctionKeys=9, BackspaceIsDelete=0,
    NemoZoomInBinding=0, NemoZoomOutBinding=0, NemoZoomDefaultsVersion=1,
    NemoAllowSetTcap=1, NemoAllowGetTcap=1)
u.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]


def compare_before(record, actual):
    expected = bytes.fromhex(record['before_reply_hex'])
    offset = record['startup_identity_bytes']
    if offset:
        assert actual.startswith(identity), ('Emulator TN changed with keyboard database', record, actual.hex())
        actual, expected = actual[len(identity):], expected[offset:]
    assert actual == expected, (record['name'], record['index'], actual.hex(), expected.hex())


try:
    for terminal in dict.fromkeys(r['terminal'] for r in reference['cases']):
        with saved_profile(dict(profile, NemoTcapName=terminal)) as profile_args, \
                tempfile.TemporaryDirectory(prefix='nemoterm-tcap-keys-') as directory, OwnedJob() as job:
            folder = Path(directory)
            report, control = folder/'report.json', folder/'control.json'
            process = job.spawn([str(exe), *profile_args, '--cols', '80', '--rows', '24', '-e', sys.executable,
                str(root/'tests/mouse_fixture.py'), str(report), str(control), '900'],
                env=dict(os.environ, NEMOTERM_CONPTY='bundled', NEMOTERM_TEST_EXACT_OUTPUT='1',
                         NEMOTERM_TEST_INPUT_CP='65001'), creationflags=subprocess.CREATE_NO_WINDOW)
            session = script = None
            observed = evidence['profiles'][terminal] = dict(pid=process.pid, completed=False)

            def current():
                value = read_snapshot(report)
                assert process.poll() is None and not value.get('error'), value
                return value

            def phase(name, sequence, record=None):
                request = dict(phase=name, sequence=sequence+'\x1b[5n', preserve_mouse=True)
                write_snapshot(control, request)
                value = wait_for(lambda: (value := current()).get('phase') == name and
                    bytes.fromhex(value.get('hex', '')).endswith(marker) and value)
                wire = bytes.fromhex(value['hex'])
                if record is None:
                    assert wire == marker, (name, value)
                else:
                    compare_before(record, wire[:-len(marker)])
                return request

            try:
                hwnd = wait_for(lambda: find_window(process.pid))
                wait_for(lambda: current().get('columns') == 80 and current().get('rows') == 24)
                session = frida.attach(process.pid)
                script = session.create_script((root/'tests/legacy_modifiers_key_probe.js').read_text())
                errors = []
                script.on('message', lambda message, data: errors.append(message) if message['type'] == 'error' else None)
                script.load()
                for record in reference['cases']:
                    if record['terminal'] != terminal:
                        continue
                    name = record['name']+'/'+str(record['index'])
                    if not record['native_comparable']:
                        evidence['excluded'][name] = record['native_exclusion']
                        continue
                    if record['reset']:
                        phase('reset-'+name, '\x1bc')
                    request = phase(name, bytes.fromhex(record['sequence_hex']).decode('ascii'), record)
                    events = record['events']
                    if events:
                        script.exports_sync.keys(dict(id=name, events=events))
                        assert u.PostMessageW(hwnd, 0x8323, 0, 0)
                        result = wait_for(lambda: script.exports_sync.result())
                        assert result == dict(id=name, count=len(events), restored=True), (result, errors)
                    assert not errors, errors
                    request['input_barrier'] = name+'-input'
                    write_snapshot(control, request)
                    value = wait_for(lambda: (value := current()).get('input_barrier') == request['input_barrier'] and value)
                    wire = bytes.fromhex(value['hex'])
                    evidence['cases'][name] = wire.hex()
                    before, keys, tail = wire.split(marker)
                    compare_before(record, before)
                    assert not tail, (name, wire.hex())
                    if keys != bytes.fromhex(record['key_reply_hex']):
                        evidence['mismatches'][name] = dict(actual_hex=keys.hex(), expected_hex=record['key_reply_hex'])
                        if len(evidence['mismatches']) <= 20:
                            print('Key mismatch:', name, evidence['mismatches'][name], flush=True)
                    if len(evidence['cases']) % 200 == 0:
                        print('Native terminfo streams:', len(evidence['cases']), flush=True)
                script.unload(); script = None
                session.detach(); session = None
                write_snapshot(control, dict(stop=True))
                process.wait(timeout=10)
                assert process.returncode == 0
                observed['cleanup'] = job.finish()
                assert not observed['cleanup']['terminated_remaining'] and observed['cleanup']['after']['active'] == 0
                observed['completed'] = True
                print('Terminfo keyboard', terminal, 'capture completed', flush=True)
            finally:
                observed['last_snapshot'] = read_snapshot(report)
                if script:
                    script.unload()
                if session:
                    session.detach()
                observed.setdefault('cleanup', job.finish(grace=0))
    assert len(evidence['cases']) == reference['native_count']
    assert len(evidence['cases'])+len(evidence['excluded']) == reference['count']
    assert not evidence['mismatches'], evidence['mismatches']
    evidence['completed'] = True
    print('Native terminfo:', len(evidence['cases']), 'streams;', len(evidence['excluded']), 'explicit native exclusions')
finally:
    (root/'research/tcap-keys-observed.json').write_text(json.dumps(evidence, indent=2))
