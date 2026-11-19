"""Hosted proof of a byte-preserving WSL input path. Never starts a shell."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


def linux_peer(length):
    import fcntl
    import select
    import struct
    import termios
    import time
    import tty

    # Any implicit Windows console would invalidate this transport comparison.
    if os.isatty(0) or os.isatty(1) or not 0 < length <= 4096:
        raise RuntimeError('expected redirected stdin/stdout and a bounded payload')
    data = sys.stdin.buffer.read(length + 1)
    if len(data) != length:
        raise ValueError('redirected stdin was changed or truncated')
    master, slave = os.openpty()
    try:
        tty.setraw(slave)
        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', 48, 160, 0, 0))
        size = os.get_terminal_size(slave)
        assert size == (160, 48) and os.isatty(slave)
        def transfer(src, dst, block):
            assert os.write(src, block) == len(block)
            output = bytearray(); end = time.monotonic()+4
            while len(output) < len(block):
                if not select.select([dst], [], [], max(0,end-time.monotonic()))[0]:
                    raise TimeoutError(('PTY timed out', output.hex()))
                fragment=os.read(dst, len(block)-len(output))
                if not fragment: raise EOFError('PTY closed')
                output.extend(fragment)
            return bytes(output)
        observed = transfer(master, slave, data)
        # Echo from the application side; the Windows parent verifies all
        # reply bytes including NUL and invalid UTF-8, not just a digest.
        response = transfer(slave, master, observed)
        meta = dict(slave=os.ttyname(slave),grid=list(size),stdin_tty=os.isatty(0),stdout_tty=os.isatty(1),
                    kernel=os.uname().release,stdin_hex=data.hex(),app_hex=observed.hex(),
                    peer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        sys.stderr.write(json.dumps(meta)+'\n')
        sys.stdout.buffer.write(response);sys.stdout.buffer.flush()
    finally:
        os.close(master);os.close(slave)


def windows_driver(root):
    import subprocess
    import zipfile
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise RuntimeError('Only run this fixture on hosted Windows')
    archive=root/'testdata/upstream/xterm412-paste-quote.zip'; results={}
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    assert digest=='3d06c7eec267dc31f6fc8c52e2fc2f0b85de3cb932f4bccca10ec31467c044c1'
    report=dict(reference_sha256=digest,cases=results);folder=root/'build/wsl-check/research';folder.mkdir(parents=True,exist_ok=True)
    def run(name,block):
        args=['wsl.exe','--distribution','Ubuntu-24.04','--cd',str(root),'--exec','/usr/bin/python3',
              'tests/wsl_pipe_pty.py','--peer',str(len(block))]
        p=subprocess.run(args,input=block,capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
        r=results[name]=dict(sent=block.hex(),received=p.stdout.hex(),exit_code=p.returncode,peer_stderr=p.stderr.decode('utf-8','replace'))
        if p.returncode==0:
            meta=json.loads(p.stderr);r.update(meta=meta,passed=p.stdout==block and meta['app_hex']==meta['stdin_hex']==block.hex()
                and meta['grid']==[160,48] and meta['peer_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        else:r['passed']=False
    try:
        with zipfile.ZipFile(archive) as z:
            for profile in ('default','custom'):
                ref=json.loads(z.read('paste-quote/'+profile+'.json'))
                for kind in ('quote','all'):
                    run(profile+'-'+kind,bytes.fromhex(ref['cases'][kind]['paste_hex'])+b'\r7')
        run('all-octets',bytes(range(256)))
    finally:
        (folder/'wsl-pipe-pty.json').write_text(json.dumps(report,indent=2))
    assert len(results)==5 and all(r['passed'] for r in results.values()), 'See byte-for-byte observations'


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--peer',type=int);args=p.parse_args()
    if args.peer is not None:
        assert sys.platform=='linux' and 'microsoft' in Path('/proc/version').read_text().lower()
        linux_peer(args.peer)
    else:windows_driver(Path(__file__).resolve().parent.parent)
