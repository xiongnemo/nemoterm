"""XTerm tabulation replies through the single-image HWND/ConPTY path."""
from native_test_utils import (root, hashlib, json, os, subprocess, sys,
    tempfile, Path, read_snapshot, write_snapshot, wait_for, find_window)
from owned_job import OwnedJob
from tabulation_oracle_cases import CASES

exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
marker = b'\x1bP0$r\x1b\\'
evidence = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                completed=False, cases={}, source_reference='XTerm(412)')
with tempfile.TemporaryDirectory(prefix='nemoterm-tabs-protocol-') as directory, OwnedJob() as job:
    folder = Path(directory)
    report, control = folder/'report.json', folder/'control.json'
    process = job.spawn([str(exe), '--cols', '80', '--rows', '24', '-e',
        sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control)],
        env=dict(os.environ, NEMOTERM_CONPTY='bundled'), creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        hwnd = wait_for(lambda: find_window(process.pid))
        def current():
            value = read_snapshot(report)
            assert process.poll() is None and not value.get('error'), value
            return value
        wait_for(lambda: current().get('columns') == 80 and current().get('rows') == 24)
        for name, sequence, expected in CASES:
            write_snapshot(control, dict(phase=name, preserve_mouse=True,
                sequence=sequence+'\x1bP$qtabulation-marker\x1b\\'))
            def received():
                value = current()
                return value if value.get('phase') == name and \
                    bytes.fromhex(value['hex']).endswith(marker) else None
            value = wait_for(received)
            wire = bytes.fromhex(value['hex'])
            evidence['cases'][name] = wire.hex()
            assert wire == expected.encode()+marker, (name, wire, expected)
        write_snapshot(control, dict(stop=True))
        process.wait(timeout=10)
        assert process.returncode == 0, process.returncode
        evidence['cleanup'] = job.finish()
        evidence['completed'] = True
        print(f'Native tabulation: {len(CASES)} XTerm cases passed')
    finally:
        evidence['last_snapshot'] = read_snapshot(report)
        (root/'research/tabulation-observed.json').write_text(json.dumps(evidence, indent=2))
