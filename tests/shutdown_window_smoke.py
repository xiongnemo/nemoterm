"""Destroy owned terminal windows before freeing their callback state at exit."""
import argparse
import frida
import uuid
import winreg
from native_test_utils import (root, u, w, hashlib, json, os, subprocess, sys,
    tempfile, Path, time, wait_for, find_window, read_snapshot, write_snapshot)
from owned_job import OwnedJob

u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--renderer', choices=('gdi', 'opengl', 'both'), default='both')
args = parser.parse_args()
exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
evidence = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), cases=[])
profile = 'shutdown-test-'+uuid.uuid4().hex
keypath = 'Software\\Nemo\\Nemoterm\\Sessions\\'+profile
try:
    renderers = ('gdi', 'opengl') if args.renderer == 'both' else (args.renderer,)
    for renderer in renderers:
        for close in ('child-exit', 'window-close'):
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, keypath) as key:
                winreg.SetValueEx(key, 'WarnOnClose', 0, winreg.REG_DWORD, 0)
                winreg.SetValueEx(key, 'CloseOnExit', 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, 'NemoRenderer', 0, winreg.REG_DWORD, int(renderer == 'opengl'))
            with tempfile.TemporaryDirectory(prefix='nemoterm-shutdown-') as tmp, OwnedJob() as job:
                report, control = Path(tmp)/'report', Path(tmp)/'control'
                process = job.spawn([str(exe), '-load', profile, '--cols', '40', '--rows', '12',
                    '-e', sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control)],
                    env=dict(os.environ, NEMOTERM_CONPTY='bundled'), creationflags=subprocess.CREATE_NO_WINDOW)
                events, session = [], None
                case = dict(renderer=renderer, close=close, events=events)
                evidence['cases'].append(case)
                try:
                    hwnd = wait_for(lambda: find_window(process.pid))
                    wait_for(lambda: read_snapshot(report))
                    case['active_renderer'] = int(u.GetPropW(hwnd, 'NemotermRenderer') or 0)
                    assert case['active_renderer'] in (1, 2), case
                    session = frida.attach(process.pid)
                    script = session.create_script((root/'tests/shutdown_probe.js').read_text())
                    script.on('message', lambda message, data: events.append(
                        message['payload'] if message['type'] == 'send' else message))
                    script.load()
                    script.exports_sync.watch(hex(hwnd))
                    if close == 'child-exit':
                        write_snapshot(control, dict(stop=True))
                    else:
                        u.PostMessageW(hwnd, 0x10, 0, 0)
                    case['exit_code'] = process.wait(timeout=10)
                    wait_for(lambda: any(e.get('event') == 'com-uninitialize' for e in events))
                    assert case['exit_code'] == 0, case
                    freed = [e for e in events if e.get('event') == 'seat-free']
                    com = [e for e in events if e.get('event') == 'com-uninitialize']
                    assert freed and all(not e['window_alive'] for e in freed), case
                    assert com and all(not e['window_alive'] and e['seat_freed'] for e in com), case
                    assert not any(e.get('event') == 'callback-after-seat-free' for e in events), case
                finally:
                    if session:
                        try: session.detach()
                        except frida.InvalidOperationError: pass
                    job.finish(grace=0)
                    process.wait(timeout=5)
finally:
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, keypath)
    (root/'research/shutdown-window-observed.json').write_text(json.dumps(evidence, indent=2))
print('Native shutdown lifetime passed:', len(evidence['cases']), 'cases')
