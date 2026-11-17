"""Run historical XTerm collectors on a hosted Linux runner.

Captures are new observations, never replacements for checked-in expectations.
Each invocation has its own output directory and a bounded process group.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


# Explicit filenames also provide an inventory of the remote entry points.
GROUPS = {
    'state': [
        ('c1-controls', 'xterm_c1_controls_oracle.py', []),
        ('dec-status', 'xterm_dec_status_oracle.py', []),
        ('presentation-state', 'xterm_presentation_state_oracle.py', []),
        ('sgr-stack', 'xterm_sgr_stack_oracle.py', []),
        ('palette-stack', 'xterm_palette_stack_oracle.py', []),
    ],
    'editing': [
        ('checksum', 'xterm_checksum_oracle.py', []),
        ('checksum-ordering', 'xterm_checksum_oracle.py', ['--ordering-probe']),
        ('double-size', 'xterm_double_size_oracle.py', []),
        ('erase', 'xterm_erase_oracle.py', []),
        ('graphics-query', 'xterm_graphics_query_oracle.py', []),
        ('horizontal', 'xterm_horizontal_oracle.py', []),
        ('margins', 'xterm_margin_oracle.py', []),
        ('rectangles', 'xterm_rectangle_oracle.py', []),
        ('reverse-wrap', 'xterm_reverse_wrap_oracle.py', []),
        ('tabulation', 'xterm_tabulation_oracle.py', []),
    ],
    'charset-mapping': [
        (f'charsets-{batch}', 'xterm_charsets_oracle.py', ['--batch', str(batch)])
        for batch in range(4)
    ],
    'charset-checksum': [('charset-checksum', 'xterm_charset_checksum_oracle.py', [])],
    'charset-state': [
        ('charset-state', 'xterm_charset_state_oracle.py', ['--isolated']),
        ('charset-lifetime', 'xterm_charset_lifetime_oracle.py', []),
        ('upss', 'xterm_upss_oracle.py', []),
    ],
    'charset-input': [
        ('charset-input', 'xterm_charset_input_oracle.py', []),
        ('charset-input-all', 'xterm_charset_input_oracle.py', ['--all-sets', '--paste-only']),
        ('charset-input-upss', 'xterm_charset_input_oracle.py', ['--upss-only', '--paste-only']),
    ],
    'keys': [
        ('extended-keys', 'xterm_extended_keys_oracle.py', []),
        ('legacy-modifiers', 'xterm_legacy_modifiers_oracle.py', []),
        ('special-keys', 'xterm_special_keys_oracle.py', []),
    ],
    'set-tcap': [('set-tcap', 'xterm_set_tcap_oracle.py', [])],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', required=True, choices=GROUPS)
    parser.add_argument('--xterm', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if (sys.platform != 'linux' or os.environ.get('GITHUB_ACTIONS') != 'true'
            or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'):
        parser.error('Reference capture requires a GitHub-hosted Linux runner')
    executable = args.xterm.resolve(strict=True)
    root = Path(__file__).resolve().parents[1]
    args.output.mkdir(parents=True, exist_ok=False)
    result = dict(group=args.group, fixture_commit=os.environ['GITHUB_SHA'],
                  run=os.environ['GITHUB_RUN_ID'],
                  executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
                  completed=False, captures=[])
    manifest = args.output / 'results.json'

    def save():
        manifest.write_text(json.dumps(result, indent=2) + '\n')

    save()
    for name, script, extra in GROUPS[args.group]:
        folder = args.output / name
        folder.mkdir()
        observed = folder / 'observed.json'
        fixture = root / 'tests' / script
        command = [sys.executable, str(fixture), '--xterm', str(executable),
                   '--output', str(observed), *extra]
        row = dict(name=name, command=command,
                   fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
                   status='running')
        result['captures'].append(row)
        save()
        started = time.monotonic()
        with (folder / 'output.log').open('w') as log:
            process = subprocess.Popen(command, cwd=root, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                row['exit_code'] = process.wait(timeout=600)
                row['status'] = 'passed' if row['exit_code'] == 0 else 'failed'
            except subprocess.TimeoutExpired:
                # Retire only the session created for this owned collector.
                row['status'] = 'timed-out'
                os.killpg(process.pid, signal.SIGKILL)
                row['exit_code'] = process.wait(timeout=10)
        row['seconds'] = round(time.monotonic() - started, 3)
        if observed.exists():
            payload = observed.read_bytes()
            row['observed_sha256'] = hashlib.sha256(payload).hexdigest()
            data = json.loads(payload)
            row['cases'] = len(data.get('cases', {}))
            row['reported_completed'] = data.get('completed')
            if (data.get('executable_sha256') != result['executable_sha256']
                    or row['cases'] == 0 or data.get('completed') is False):
                row['status'] = 'failed'
                row['validation_error'] = 'Incomplete or mismatched reference capture'
        else:
            row['status'] = 'failed'
            row['validation_error'] = 'No reference observation was produced'
        print(name, row['status'], row.get('cases', 0), flush=True)
        save()
    result['completed'] = True
    save()
    return int(any(row['status'] != 'passed' for row in result['captures']))


if __name__ == '__main__':
    raise SystemExit(main())
