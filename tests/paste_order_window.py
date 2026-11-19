"""Collect the exact UTF-16 delivered to a native child by two overlapping pastes."""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import traceback
import uuid
import winreg

from fixture_io import write_snapshot
from native_test_utils import wait_for
from owned_job import OwnedJob

ROOT = Path(__file__).resolve().parents[1]
OPEN, CLOSE = '\x1b[200~', '\x1b[201~'
SECOND = 'SECOND:尾🙂:END'
QUIT = 'QUIT-RECEIVER'


def wide(s):
    return s.encode('utf-16-le')


def child(folder, bracketed):
    k = c.windll.kernel32
    k.GetStdHandle.argtypes = [w.DWORD]; k.GetStdHandle.restype = w.HANDLE
    k.SetConsoleMode.argtypes = [w.HANDLE, w.DWORD]
    k.ReadConsoleW.argtypes = [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p]
    inp, out = k.GetStdHandle(-10), k.GetStdHandle(-11)
    assert k.SetConsoleMode(inp, 0x200) and k.SetConsoleMode(out, 7)
    os.write(1, b'\x1b[?2004' + (b'h' if bracketed else b'l') + b'PASTE_RECEIVER_READY')
    buf, count = c.create_string_buffer(8192), w.DWORD()
    suffix = b''
    with (folder/'received.utf16le').open('wb', buffering=0) as sink:
        while True:
            assert k.ReadConsoleW(inp, buf, 4096, c.byref(count), None) and count.value
            chunk = buf.raw[:2*count.value]; sink.write(chunk)
            suffix = (suffix + chunk)[-len(wide(QUIT)):]
            if suffix == wide(QUIT):
                return


def parent():
    sys.path.insert(0, str(ROOT/'tools'))
    import nemoterm_debug as api
    exe = Path(os.environ['NEMOTERM_TEST_EXE']).resolve(strict=True)
    base = ROOT/'build/focused-evidence/paste-order'; base.mkdir(parents=True, exist_ok=False)
    first = ''.join(f'A{i:04d}\r\n' for i in range(4096)) + 'FIRST-END:中'
    result = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), cases=[])
    for renderer, number in [('gdi', 0), ('directx', 2)]:
        for bracketed in (False, True):
            folder = base/(renderer + ('-bracketed' if bracketed else '-plain')); folder.mkdir()
            r = dict(renderer=renderer, bracketed=bracketed, passed=False); result['cases'].append(r)
            def frame(s): return OPEN+s+CLOSE if bracketed else s
            expected = wide(frame(first.replace('\r\n','\r')) + frame(SECOND) + QUIT)
            (folder/'expected.utf16le').write_bytes(expected)
            profile = 'paste-'+uuid.uuid4().hex; key = 'Software\\Nemo\\Nemoterm\\Sessions\\'+profile
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as cfg:
                for name, val in dict(NemoRenderer=number, WarnOnClose=0, CloseOnExit=1).items():
                    winreg.SetValueEx(cfg, name, 0, winreg.REG_DWORD, val)
            try:
                with OwnedJob() as job:
                    p = job.spawn([str(exe),'--tabs','--automation','-load',profile,'--font',os.environ['NEMOTERM_TEST_FONT'],'-e',sys.executable,__file__,'child',str(folder),str(int(bracketed))],env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
                    inst = wait_for(lambda: next(iter(api.discover(p.pid)),None), timeout=20)
                    seat, = inst['sessions']; assert seat['renderer'] == number
                    def send(op, payload=b''): return api.request(inst['endpoint'], op, seat['id'], payload)
                    wait_for(lambda: 'PASTE_RECEIVER_READY' in send('text'))
                    send('paste', first); send('paste', SECOND)
                    path = folder/'received.utf16le'
                    # Wait for a distinctive terminal suffix before injecting the independent
                    # quit barrier: typing the barrier too soon would itself cancel a paste.
                    suffix = wide(SECOND + (CLOSE if bracketed else ''))
                    wait_for(lambda: path.exists() and path.read_bytes().endswith(suffix), timeout=50)
                    send('input', QUIT)
                    r.update(exit_code=p.wait(timeout=12), cleanup=job.finish())
                    assert r['exit_code']==0 and not r['cleanup']['terminated_remaining']
            except Exception:
                r['error'] = traceback.format_exc()
            finally:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER,key)
                path = folder/'received.utf16le'; actual = path.read_bytes() if path.exists() else b''
                r.update(expected_bytes=len(expected), received_bytes=len(actual), expected_sha256=hashlib.sha256(expected).hexdigest(), received_sha256=hashlib.sha256(actual).hexdigest(),
                         first_mismatch_byte=next((i for i,(a,b) in enumerate(zip(expected,actual)) if a!=b), min(len(expected),len(actual)) if actual!=expected else None),
                         starts=actual.count(wide(OPEN)), ends=actual.count(wide(CLOSE)), passed='error' not in r and actual==expected)
                write_snapshot(base/'summary.json',result); print(r,flush=True)
    return int(not all(r['passed'] for r in result['cases']))


if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    if sys.argv[1:2]==['child']: child(Path(sys.argv[2]), bool(int(sys.argv[3])))
    else: sys.exit(parent())
