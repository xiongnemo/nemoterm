"""Run bounded query/reply fixtures through an owned native terminal job."""
from native_test_utils import (root, hashlib, json, os, subprocess, sys,
    tempfile, Path, time, read_snapshot, write_snapshot, wait_for, find_window, capture)
from owned_job import OwnedJob
from contextlib import contextmanager


@contextmanager
def saved_profile(values):
    if values is None:
        yield []
        return
    import uuid
    import winreg
    name = 'protocol-test-'+uuid.uuid4().hex
    keypath = 'Software\\Nemo\\Nemoterm\\Sessions\\'+name
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, keypath) as key:
            for setting, value in values.items():
                kind = winreg.REG_SZ if isinstance(value, str) else winreg.REG_DWORD
                winreg.SetValueEx(key, setting, 0, kind, value)
        yield ['-load', name]
    finally:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, keypath)


def run(name, cases, scene=None, extra_cases=(), exercise=None, barrier=None, report_cursor=False,
        profile=None, font=None, source_reference='XTerm(412)'):
    exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
    barrier_sequence, marker = barrier or ('\x1bP$qprotocol-marker\x1b\\', b'\x1bP0$r\x1b\\')
    evidence = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                    completed=False, cases={}, source_reference=source_reference,
                    reference_case_count=len(cases), direct_case_names=[c[0] for c in extra_cases])
    evidence['profile_values'] = profile
    if font is not None:evidence['requested_font'] = font
    with saved_profile(profile) as profile_args, \
            tempfile.TemporaryDirectory(prefix='nemoterm-'+name+'-') as directory, OwnedJob() as job:
        folder = Path(directory)
        report, control = folder/'report.json', folder/'control.json'
        font_args = ['--font', font] if font is not None else []
        process = job.spawn([str(exe), *profile_args, '--cols', '80', '--rows', '24', *font_args, '-e',
            sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control), '180'],
            env=dict(os.environ, NEMOTERM_CONPTY='bundled', NEMOTERM_TEST_EXACT_OUTPUT='1'),
            creationflags=subprocess.CREATE_NO_WINDOW)
        wire_trace = None
        try:
            hwnd = wait_for(lambda: find_window(process.pid))
            def snapshot():
                value = read_snapshot(report)
                assert process.poll() is None and not value.get('error'), value
                # Windows can briefly deny a mailbox read during replacement.
                # Every caller needs the same complete snapshot, including
                # geometry checks after an owned-window resize.
                return value or None
            def current():
                return wait_for(snapshot)
            wait_for(lambda: current().get('columns') == 80 and current().get('rows') == 24)
            if os.environ.get('NEMOTERM_PROTOCOL_WIRE_TRACE') == '1':
                from protocol_wire_trace import ProtocolWireTrace
                wire_trace = ProtocolWireTrace(process, exe, root/'research'/f'{name}-wire.jsonl')
            def phase(phase_name, sequence, expected, phase_barrier=None):
                active_barrier,active_marker = phase_barrier or (barrier_sequence,marker)
                expected_bytes = expected if isinstance(expected, bytes) else expected.encode() if expected is not None else None
                if wire_trace:
                    wire_trace.phase(phase_name, sequence+active_barrier,
                                     expected_bytes+active_marker if expected_bytes is not None else None)
                write_snapshot(control, dict(phase=phase_name, preserve_mouse=True, report_cursor=report_cursor,
                    sequence=sequence+active_barrier))
                def received():
                    value = current()
                    return value if value.get('phase') == phase_name and \
                        bytes.fromhex(value['hex']).endswith(active_marker) else None
                value = wait_for(received)
                wire = bytes.fromhex(value['hex'])
                evidence['cases'][phase_name] = wire.hex()
                evidence.setdefault('case_metadata',{})[phase_name] = dict(
                    input_cp=value.get('input_cp'),input_api=value.get('input_api'))
                if expected is not None:
                    assert wire == expected_bytes+active_marker, (phase_name, wire, expected)
                return wire[:-len(active_marker)]
            for phase_name, sequence, expected in tuple(cases)+tuple(extra_cases):
                phase(phase_name, sequence, expected)
            if exercise is not None:
                evidence['exercise'] = exercise(hwnd, phase, current)
            if scene is not None:
                phase('visible-scene', scene, '')
                time.sleep(.2)
                capture(hwnd, name+'-window.png')
            write_snapshot(control, dict(stop=True))
            process.wait(timeout=10)
            assert process.returncode == 0, process.returncode
            if wire_trace:
                evidence['wire_observer'] = wire_trace.close()
                wire_trace = None
                assert not evidence['wire_observer']['errors'], evidence['wire_observer']
                assert not evidence['wire_observer']['truncated'], evidence['wire_observer']
            evidence['cleanup'] = job.finish()
            assert not evidence['cleanup']['terminated_remaining'], evidence['cleanup']
            evidence['completed'] = True
            print(f'Native {name}: {len(cases)} XTerm and {len(extra_cases)} direct cases passed')
        finally:
            evidence['last_snapshot'] = read_snapshot(report)
            try:
                if wire_trace:
                    # This observer hooks blocking ReadFile calls. Detaching a
                    # live blocked invocation can stall Frida script teardown.
                    # On failure drain this private job first (the same cleanup
                    # the context manager would perform), preserving the failed
                    # snapshot above. A successful run requires natural exit.
                    evidence['cleanup'] = job.finish()
                    evidence['wire_observer'] = wire_trace.close()
            finally:
                evidence.setdefault('cleanup',job.finish(grace=0))
                (root/'research'/f'{name}-observed.json').write_text(json.dumps(evidence, indent=2))
