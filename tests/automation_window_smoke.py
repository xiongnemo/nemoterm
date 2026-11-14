"""Exercise the public local API against owned real terminal/ConPTY windows."""
import ctypes as c
import argparse
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import uuid
import winreg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'tools'))


def child():
    import msvcrt
    from fixture_io import write_snapshot
    k = c.windll.kernel32
    k.GetStdHandle.argtypes = [w.DWORD]; k.GetStdHandle.restype = w.HANDLE
    k.SetConsoleMode.argtypes = [w.HANDLE, w.DWORD]
    # The fixture writes UTF-8 bytes; do not inherit the runner's OEM code page.
    assert k.SetConsoleCP(65001)
    assert k.SetConsoleOutputCP(65001)
    handle = k.GetStdHandle(-10)
    assert k.SetConsoleMode(handle, 0x200)
    assert k.SetConsoleMode(k.GetStdHandle(-11), 7)
    os.write(1, ('\x1b[2J\x1b[H\x1b[?25l\x1b[?2004hNEMOTERM_DEBUG_READY '
                 f'{os.getpid()}\r\n中文 e\u0301 😀\r\n').encode())
    data = bytearray()
    while True:
        data.extend(os.read(0, 4096))
        write_snapshot(Path(sys.argv[2])/f'child-{os.getpid()}.json', {'hex': data.hex()})
        if data.endswith(b'quit\r'):
            break


def main():
    import nemoterm_debug as api
    from owned_job import OwnedJob
    from native_test_utils import wait_for, memory_sample, capture, u
    from fixture_io import read_snapshot, write_snapshot
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--renderer', choices=('gdi','directx'), default='gdi')
    args=parser.parse_args()
    exe = Path(os.environ.get('NEMOTERM_TEST_EXE', ROOT/'dist/nemoterm.exe')).resolve()
    folder = Path(tempfile.mkdtemp(prefix='automation-', dir=ROOT/'build'))
    profile = 'automation-'+uuid.uuid4().hex
    registry = 'Software\\Nemo\\Nemoterm\\Sessions\\'+profile
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, registry) as key:
        for name, value in [('WarnOnClose', 0), ('NemoRenderer', 2 if args.renderer=='directx' else 0), ('CloseOnExit', 1)]:
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
    result = {'exe_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(), 'folder': str(folder),
              'requested_renderer': args.renderer, 'checks': []}
    def checked(name):
        result['checks'].append(name);print(name, flush=True)
    try:
        with OwnedJob() as job:
            command = [str(exe), '-load', profile, '--cols', '80', '--rows', '24',
                       '--font', 'Consolas', '--shell-command', subprocess.list2cmdline(
                           [sys.executable, str(Path(__file__).resolve()), '--child', str(folder)])]
            process = job.spawn(command[:3]+['--automation', '--tabs']+command[3:], creationflags=subprocess.CREATE_NO_WINDOW)
            instance = wait_for(lambda: next(iter(api.discover(process.pid)), None), timeout=20)
            endpoint = instance['endpoint']; seat = instance['sessions'][0]['id']
            result['actual_renderer'] = instance['sessions'][0]['renderer']
            assert result['actual_renderer'] == (2 if args.renderer=='directx' else 0), instance
            text = wait_for(lambda: (t if 'NEMOTERM_DEBUG_READY' in (t := api.request(endpoint, 'text', seat)) else None))
            assert '中文 e\u0301 😀' in text, repr(text)
            result['io_contexts'] = []
            def io_contexts(expected):
                def snapshot():
                    value = api.request(endpoint)['io_handles']
                    assert value['created']-value['destroyed'] == value['input']+value['output']
                    assert 0 <= value['closing'] <= value['input']+value['output']
                    return value if value['input'] == value['output'] == expected and value['closing'] == 0 else None
                value = wait_for(snapshot)
                result['io_contexts'].append(value)
                return value
            io_before = io_contexts(1)
            # Text parsing precedes the scheduled presentation frame.
            time.sleep(.15)
            checked('discover, stable session ID and Unicode logical screen')
            image = api.request(endpoint, 'image', seat)
            (folder/'api.png').write_bytes(api.png_from_bmp(image))
            result['memory_before_reference_capture'] = memory_sample(int(process._handle))
            result['memory_instrumented'] = args.renderer=='directx'
            if args.renderer=='directx':
                # Cross-process PrintWindow cannot capture this child GPU
                # surface. Compare with the pre-existing owned GPU probe.
                from gpu_capture import OwnedGPUCapture
                probe=OwnedGPUCapture(process.pid,instance['sessions'][0]['hwnd'])
                try:
                    reference=probe.capture(str(folder/'reference.png'),True)
                finally:
                    probe.close()
            else:
                reference = capture(instance['sessions'][0]['hwnd'], str(folder/'reference.png'),
                                    return_pixels=True, print_flags=1)
            bgra=image[54:];rgb=bytearray(len(bgra)//4*3)
            rgb[0::3],rgb[1::3],rgb[2::3]=bgra[2::4],bgra[1::4],bgra[0::4]
            assert len(rgb)==len(reference)
            # DirectWrite fallback glyph edges can round by one channel value
            # when PrintWindow copies the composed surface into another DC.
            deltas=[abs(a-b) for a,b in zip(rgb,reference)]
            result['capture_max_channel_delta']=max(deltas,default=0)
            result['capture_differing_channels']=sum(d!=0 for d in deltas)
            assert result['capture_max_channel_delta']<=1, 'API pixels differ from the native window capture'
            result['image_sha256'] = hashlib.sha256(image).hexdigest()
            result['memory_initial'] = memory_sample(int(process._handle))
            checked('pixel screenshot without clipboard or foreground input')
            for operation, payload in [('input', 'hello中'), ('paste', 'pasted value'),
                                       ('key', struct.pack('<II', 13, 0))]:
                api.request(endpoint, operation, seat, payload)
                time.sleep(.2)
            def received():
                values = [read_snapshot(p) for p in folder.glob('child-*.json')]
                return next((bytes.fromhex(v['hex']) for v in values if v and 'hex' in v), b'')
            data = wait_for(lambda: (v if b'pasted value' in (v := received()) and v.endswith(b'\r') else None))
            assert 'hello中'.encode() in data, data
            assert b'\x1b[200~pasted value\x1b[201~' in data, data
            result['input_hex'] = data.hex()
            checked('UTF-8 input, bracketed paste and Enter key reach the real child')
            for op, sid, payload, status in [('text', seat+999, b'', 2), ('input', seat, b'\xff', 1),
                                            ('key', seat, b'x', 1), ('text', seat, b'x', 1)]:
                try:
                    api.request(endpoint, op, sid, payload)
                    raise AssertionError('Expected explicit rejection')
                except api.DebugError as exc:
                    assert exc.status == status
            checked('stale target and malformed requests are rejected')
            # An abandoned partial request has a deadline and cannot wedge the server.
            handle = api.connect(endpoint)
            api._transfer(handle, b'NDBG', write=True)
            api.k.CloseHandle(handle)
            assert api.request(endpoint)['pid'] == process.pid
            handle = api.connect(endpoint)
            api._transfer(handle, struct.pack('<4sHHQII', b'NDBG', 1, 3, seat, 65537, 0), write=True)
            try:
                api._transfer(handle, 16)
                raise AssertionError('Oversized frame was accepted')
            except (OSError, EOFError):
                pass
            finally:
                api.k.CloseHandle(handle)
            assert api.request(endpoint)['pid'] == process.pid
            checked('partial disconnect and oversized frames leave the service usable')
            handle = api.connect(endpoint)
            api._transfer(handle, b'NDBG', write=True)
            # A stalled transport client does not block the terminal UI thread.
            u.SendMessageW(instance['sessions'][0]['hwnd'], 0x102, ord('!'), 1)
            wait_for(lambda: received().endswith(b'!'))
            time.sleep(5.1)
            api.k.CloseHandle(handle)
            assert api.request(endpoint)['pid'] == process.pid
            checked('idle client timeout keeps the window and subsequent discovery responsive')
            api.request(endpoint, 'key', seat, struct.pack('<II', ord('T'), 3))
            sessions = wait_for(lambda: (s if len(s := api.request(endpoint)['sessions']) == 2 else None))
            second = next(s['id'] for s in sessions if s['id'] != seat)
            wait_for(lambda: 'NEMOTERM_DEBUG_READY' in api.request(endpoint, 'text', second))
            io_open = io_contexts(2)
            assert io_open['created'] == io_before['created']+2
            assert len(api.request(endpoint, 'image', seat)) > 54
            api.request(endpoint, 'input', second, 'quit\r')
            wait_for(lambda: len(api.request(endpoint)['sessions']) == 1)
            io_closed = io_contexts(1)
            assert io_closed['destroyed'] == io_before['destroyed']+2
            checked('I/O context statistics return to baseline after tab shutdown')
            try:
                api.request(endpoint, 'input', second, 'must not reach another tab')
                raise AssertionError('Closed tab ID was accepted')
            except api.DebugError as exc:
                assert exc.status == 2
            checked('multiple tabs, inactive capture and closed-tab targeting')
            result['memory_after_capture'] = memory_sample(int(process._handle))
            api.request(endpoint, 'input', seat, 'quit\r')
            assert process.wait(timeout=15) == 0
            assert api.discover(process.pid) == []
            result['cleanup'] = job.finish()
            assert not result['cleanup']['terminated_remaining'], result['cleanup']
            checked('natural shutdown removes discovery endpoint and drains owned children')
        # Same executable, no flag: no automation pipe.
        with OwnedJob() as job:
            process = job.spawn(command, creationflags=subprocess.CREATE_NO_WINDOW)
            time.sleep(1)
            assert api.discover(process.pid) == []
            from native_test_utils import find_window
            hwnd = wait_for(lambda: find_window(process.pid))
            for char in 'quit\r':
                u.SendMessageW(hwnd, 0x102, ord(char), 1)
            assert process.wait(timeout=15) == 0
            assert not job.finish()['terminated_remaining']
            checked('automation is opt-in')
        result['completed'] = True
    finally:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, registry)
        (ROOT/'research').mkdir(exist_ok=True)
        write_snapshot(ROOT/f'research/automation-{args.renderer}-observed.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    child() if len(sys.argv)>1 and sys.argv[1]=='--child' else main()
