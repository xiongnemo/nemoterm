"""Repeat the existing Git Bash duplicate/close case on a hosted desktop.

Ordinary and read-only process-observed cases use the same product and original
three-second job drain. Every attempt remains recorded, including failures.
"""
import argparse
import os
from pathlib import Path
import subprocess

from interaction_acceptance import digest, load, prepare, require_remote_runner, run, save


def main():
    require_remote_runner()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--iterations', type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.iterations <= 32:
        parser.error('Expected 1 to 32 iterations per observer mode')
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    exe = args.exe.resolve(strict=True)
    if digest(exe) != args.sha256:
        raise ValueError('Product SHA-256 mismatch')
    evidence = dict(executable_sha256=args.sha256, iterations_per_mode=args.iterations,
        fixture_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        completed=False, cases=[])
    os.environ['NEMOTERM_TEST_SHELL'] = 'git-bash'
    os.environ['NEMOTERM_REQUIRED_SHELLS'] = 'git-bash'
    os.environ.pop('NEMOTERM_TEST_WSL_DISTRO', None)
    try:
        for iteration in range(args.iterations):
            # Interleave the modes rather than running all observed cases last.
            for mode in ('ordinary', 'process-observed'):
                os.environ['NEMOTERM_SHELL_PROCESS_OBSERVER'] = '0' if mode == 'ordinary' else '1'
                stage = destination/f'{iteration+1:02d}-{mode}'
                prepare(argparse.Namespace(stage=stage, exe=exe, sha256=args.sha256,
                    codex=None, opencode=None))
                code = run(argparse.Namespace(stage=stage, group=['shells'], case=[],
                    continue_on_failure=True, retry_failed=False))
                result = load(stage/'results.json')
                if len(result) != 1:
                    raise ValueError('Expected exactly one retained shell attempt')
                evidence['cases'].append(dict(iteration=iteration+1, observer=mode,
                    directory=stage.name, result=result[0], exit_code=code))
                save(destination/'summary.json', evidence)
        evidence['completed'] = True
    finally:
        save(destination/'summary.json', evidence)
    failures = [c['directory'] for c in evidence['cases'] if c['exit_code']]
    print('Failed shell lifetimes:', failures, flush=True)
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
