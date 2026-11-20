"""Run the same WSL launcher and pipe topology with and without the PTY, without Nemoterm."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

from owned_job import OwnedJob
from wsl_job_observation import job_images, finish_observed


def main(relay, output):
    assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
    digest = hashlib.sha256(relay.read_bytes()).hexdigest()
    assert relay.with_name('SHA256SUMS').read_text().strip() == digest + '  relay'
    launcher = str(Path(os.environ['SystemRoot'])/'System32/wsl.exe')
    wsl = [launcher, '--distribution', os.environ['NEMOTERM_TEST_WSL_DISTRO'], '--exec']
    guest = ['/usr/bin/printf', 'NEMO_WSL_EXIT']
    # Same path conversion and argument positions as the bundled launch. Use
    # pipes for both controls and leave stdin open until the launcher exits.
    wrapper = 'p=$(wslpath -a -u "$1") || exit 125; shift; exec "$p" "$@"'
    cases = [('direct', guest), ('with-relay', ['/bin/sh', '-c', wrapper, 'nemoterm', str(relay),
              '--pixels', '80', '24', '640', '384', *guest])]
    report = dict(launcher=launcher, relay_sha256=digest, cases={})
    for name, cmd in cases:
        row = report['cases'][name] = dict(guest_argv=cmd)
        try:
            with OwnedJob() as job:
                proc = job.spawn(wsl + cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    row['exit_code'] = proc.wait(timeout=30)
                    row['job_after_exit'] = job_images(job)
                finally:
                    row['cleanup'] = finish_observed(job)
                    out, err = proc.communicate(timeout=5)
                    row.update(stdout_hex=out.hex(), stderr_hex=err.hex())
                row['guest_ok'] = row['exit_code'] == 0 and out == b'NEMO_WSL_EXIT'
        except Exception:
            row['error'] = traceback.format_exc()
        finally:
            output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return all(r.get('guest_ok') and not r['cleanup']['grace_exceeded'] and not r['cleanup']['terminated_remaining']
               for r in report['cases'].values())


if __name__ == '__main__':
    sys.exit(0 if main(Path(sys.argv[1]).resolve(strict=True), Path(sys.argv[2])) else 1)
