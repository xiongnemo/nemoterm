"""Check first-use shell discovery on a fresh hosted Windows runner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import winreg


PROFILE = r'Software\Nemo\Nemoterm\Sessions\Default%20Settings'
SHELLS = {'powershell', 'pwsh', 'cmd', 'busybox-ash', 'git-bash', 'wsl-bash'}


def has_default():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PROFILE):
            return True
    except FileNotFoundError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('product', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        parser.error('Requires an isolated GitHub-hosted Windows runner')
    exe = (args.product/'nemoterm.exe').resolve(strict=True)
    manifest = json.loads((args.product/'SOURCE-HOST.json').read_text(encoding='utf-8-sig'))
    assert manifest['Executable'] == {'SHA256': hashlib.sha256(exe.read_bytes()).hexdigest(), 'Bytes': exe.stat().st_size}
    result = dict(source=manifest, fixture=os.environ['GITHUB_SHA'], had_default=has_default(), runs=[], passed=False)
    try:
        if result['had_default']:
            raise ValueError('The runner already had a Default Profile; no first-use observation is possible')
        for argv in (['--no-tabs', '--list-shells'], ['--list-shells'], ['--tabs', '--list-shells']):
            run = dict(argv=argv, had_default=has_default()); result['runs'].append(run)
            start = time.monotonic()
            with subprocess.Popen([str(exe), *argv], stdout=subprocess.PIPE) as child:
                try:
                    output, _ = child.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    run.update(deadline_seconds=10, status_at_deadline=child.poll())
                    child.kill(); child.wait(timeout=5)
                    raise
                finally:
                    run.update(elapsed_seconds=time.monotonic()-start, has_default=has_default())
                run['exit_code'] = child.returncode
                run['stdout'] = output.decode('utf-8')
                rows = json.loads(run['stdout'])
                assert child.returncode == 0 and {row['id'] for row in rows} == SHELLS and len(rows) == len(SHELLS)
                assert {'powershell','cmd'} <= {row['id'] for row in rows if row['available'] and Path(row['path']).is_file()}
        # As a child argument the same word must be delivered literally. This
        # ordinary terminal launch should also create Default on first use.
        marker = args.output.with_suffix('.child.txt').resolve()
        if marker.exists():
            raise ValueError('Child marker must be fresh')
        child_script = 'import pathlib,sys; pathlib.Path(sys.argv[1]).write_text(sys.argv[2], encoding="ascii")'
        with subprocess.Popen([str(exe), '--no-tabs', '-e', sys.executable, '-c',
                               child_script, str(marker), '--list-shells']) as frontend:
            try:
                exit_code = frontend.wait(timeout=15)
            except subprocess.TimeoutExpired:
                frontend.kill(); frontend.wait(timeout=5); raise
        control = dict(exit_code=exit_code, argument=marker.read_text(encoding='ascii') if marker.exists() else None,
                       has_default=has_default())
        result['child_control'] = control
        result['passed'] = (not any(run['has_default'] for run in result['runs']) and
                            len({run['stdout'] for run in result['runs']}) == 1 and
                            control == dict(exit_code=0, argument='--list-shells', has_default=True))
        return 0 if result['passed'] else 1
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        for run in result['runs']:
            print(run['argv'], 'seconds:', run.get('elapsed_seconds'), 'Default Profile present:', run.get('has_default'))


if __name__ == '__main__':
    raise SystemExit(main())
