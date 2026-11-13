"""Run bounded query/reply fixtures through an owned native terminal job."""
from native_test_utils import (root, hashlib, json, os, subprocess, sys,
    tempfile, Path, time, read_snapshot, write_snapshot, wait_for, find_window, capture)
from owned_job import OwnedJob


def run(name, cases, scene=None, extra_cases=(), exercise=None, barrier=None, report_cursor=False):
    exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
    barrier_sequence, marker = barrier or ('\x1bP$qprotocol-marker\x1b\\', b'\x1bP0$r\x1b\\')
    evidence = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                    completed=False, cases={}, source_reference='XTerm(412)',
                    reference_case_count=len(cases), direct_case_names=[c[0] for c in extra_cases])
    with tempfile.TemporaryDirectory(prefix='nemoterm-'+name+'-') as directory, OwnedJob() as job:
        folder = Path(directory)
        report, control = folder/'report.json', folder/'control.json'
        process = job.spawn([str(exe), '--cols', '80', '--rows', '24', '-e',
            sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control)],
            env=dict(os.environ, NEMOTERM_CONPTY='bundled', NEMOTERM_TEST_EXACT_OUTPUT='1'),
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            hwnd = wait_for(lambda: find_window(process.pid))
            def current():
                value = read_snapshot(report)
                assert process.poll() is None and not value.get('error'), value
                return value
            wait_for(lambda: current().get('columns') == 80 and current().get('rows') == 24)
            def phase(phase_name, sequence, expected):
                write_snapshot(control, dict(phase=phase_name, preserve_mouse=True, report_cursor=report_cursor,
                    sequence=sequence+barrier_sequence))
                def received():
                    value = current()
                    return value if value.get('phase') == phase_name and \
                        bytes.fromhex(value['hex']).endswith(marker) else None
                value = wait_for(received)
                wire = bytes.fromhex(value['hex'])
                evidence['cases'][phase_name] = wire.hex()
                if expected is not None:
                    assert wire == expected.encode()+marker, (phase_name, wire, expected)
                return wire[:-len(marker)]
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
            evidence['cleanup'] = job.finish()
            evidence['completed'] = True
            print(f'Native {name}: {len(cases)} XTerm and {len(extra_cases)} direct cases passed')
        finally:
            evidence['last_snapshot'] = read_snapshot(report)
            (root/'research'/f'{name}-observed.json').write_text(json.dumps(evidence, indent=2))
