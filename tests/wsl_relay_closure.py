"""Close a hosted relay with a full tty, or after the child closes its tty.

The owner runs inside the selected kernel, so descriptors and closure refer to
actual Linux pipes (not a WSL launcher's forwarding buffers). No desktop use.
"""
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import struct
import subprocess
import sys
import tempfile
import time
import traceback
import tty

ROOT = Path(__file__).resolve().parents[1]
RELAY = ROOT / 'build/wsl-relay/relay'


def peer(mode, ready):
    assert all(os.isatty(fd) for fd in (0, 1, 2))
    tty.setraw(0)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    signal.alarm(9)  # bounded fallback even if the old relay never notices closure
    if mode.startswith('tty-first'):
        for fd in (0, 1, 2):
            os.close(fd)
    ready.write_text(str(os.getpid()))
    if mode == 'tty-first-natural':
        time.sleep(.7)
        return 37
    while True:
        signal.pause()


def exercise(mode, record, ready):
    start = time.monotonic()
    with subprocess.Popen([str(RELAY), '80', '24', sys.executable, __file__, '--peer', mode, str(ready)],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0) as proc:
        try:
            while not (ready.exists() and ready.stat().st_size):
                if time.monotonic() - start >= 5 or proc.poll() is not None:
                    raise TimeoutError('peer never reached its declared state')
                time.sleep(.02)
            pid = int(ready.read_text())
            record['peer_pid'] = pid
            if mode == 'full-input':
                # Writes <= PIPE_BUF are atomic on Linux. Refuse to close
                # until the producer has seen sustained backpressure.
                fd = proc.stdin.fileno()
                os.set_blocking(fd, False)
                packet = struct.pack('>BH', 1, 1024) + b'x' * 1024
                count = 0
                while time.monotonic() - start < 5:
                    try:
                        assert os.write(fd, packet) == len(packet)
                        count += 1
                    except BlockingIOError:
                        if not select.select([], [fd], [], .35)[1]:
                            break
                else:
                    raise AssertionError('input never remained full')
                record['frames_sent'] = count
                assert count > 0
            close_time = time.monotonic()
            if mode == 'reader-gone':
                proc.stdout.close()
            elif mode != 'tty-first-natural':
                proc.stdin.close()
            wanted = 37 if mode == 'tty-first-natural' else 137
            try:
                record['exit'] = proc.wait(timeout=4)
            finally:
                record['observed_seconds'] = round(time.monotonic() - close_time, 3)
            assert record['exit'] == wanted
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                record['child_reaped'] = True
            else:
                raise AssertionError('peer still exists after the relay returned')
            assert not proc.stderr.read()
            record['passed'] = True
        finally:
            if proc.poll() is None:
                # Preserve the failure. The fixture's own bounded SIGALRM
                # allows even the unmodified relay to reap the child itself.
                try:
                    record['late_exit'] = proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    record['forced_relay_exit'] = proc.wait(timeout=2)


def main(host):
    assert os.environ.get('NEMO_HOSTED_PTY_FIXTURE') == '1' and sys.platform == 'linux'
    kernel = Path('/proc/version').read_text()
    assert (host == 'wsl1') == ('microsoft' in kernel.lower())
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    report = dict(host=host, kernel=kernel, relay_sha256=sha(RELAY), fixture_sha256=sha(Path(__file__)), cases={})
    dest = ROOT/'build/wsl-relay-records'/('closure-'+host+'.json')
    dest.parent.mkdir(exist_ok=True, parents=True)
    with tempfile.TemporaryDirectory() as folder:
        for mode in ('full-input', 'reader-gone', 'tty-first-close', 'tty-first-natural'):
            record = report['cases'][mode] = {'passed': False}
            try:
                exercise(mode, record, Path(folder)/mode)
            except Exception:
                record['error'] = traceback.format_exc()
            dest.write_text(json.dumps(report, indent=2)+'\n')
    assert all(r['passed'] for r in report['cases'].values()), report


if __name__ == '__main__':
    if sys.argv[1] == '--peer':
        sys.exit(peer(sys.argv[2], Path(sys.argv[3])))
    main(sys.argv[1])
