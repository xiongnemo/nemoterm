"""Destroy owned terminal windows before freeing their callback state at exit."""
import argparse
import atexit
import faulthandler
import frida
import itertools
import uuid
import winreg
from native_test_utils import (root, c, u, w, hashlib, json, os, subprocess, sys,
    tempfile, Path, time, wait_for, find_window, read_snapshot, write_snapshot)
from owned_job import OwnedJob
from owned_failure_state import record_owned_failure
from frida_test_utils import detach_session

u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE
u.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
u.PostMessageW.argtypes, u.PostMessageW.restype = [w.HWND, w.UINT, w.WPARAM, w.LPARAM], w.BOOL

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--renderer', choices=('gdi', 'opengl', 'directx', 'both', 'all'), default='all')
parser.add_argument('--observer', choices=('lifetime', 'none', 'both', 'session'), default='both',
                    help='lifetime/none are ordinary paired checks; session is an attach-only diagnosis')
parser.add_argument('--failure-dump', type=Path,
                    help='optional diagnostic helper, invoked only after a failed live-process check')
args = parser.parse_args()
exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
evidence = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                cases=[], completed=False)
evidence_path = root/'research/shutdown-window-observed.json'
# Only enabled by CI. A stuck instrumentation call must fail with a stack and
# leave the remaining job time for artifact upload. Windows closes OwnedJob's
# kill-on-close handles even on this watchdog's immediate process exit.
if deadline := os.environ.get('NEMOTERM_SHUTDOWN_DEADLINE_SECONDS'):
    faulthandler.dump_traceback_later(float(deadline), exit=True)
    atexit.register(faulthandler.cancel_dump_traceback_later)

def checkpoint(case, phase):
    case['phase'] = phase
    case.setdefault('phases', []).append(dict(name=phase, monotonic=time.monotonic()))
    write_snapshot(evidence_path, evidence)
    print(f"Shutdown {case['renderer']} {case['close']}: {phase}", flush=True)

profile = 'shutdown-test-'+uuid.uuid4().hex
keypath = 'Software\\Nemo\\Nemoterm\\Sessions\\'+profile
evidence['temporary_registry_key'] = keypath
try:
    renderers = ('gdi', 'opengl', 'directx') if args.renderer == 'all' else (
        ('gdi', 'opengl') if args.renderer == 'both' else (args.renderer,))
    for renderer in renderers:
        observers = ('none', 'lifetime') if args.observer == 'both' else (args.observer,)
        for close, observer in itertools.product(('child-exit', 'window-close'), observers):
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, keypath) as key:
                winreg.SetValueEx(key, 'WarnOnClose', 0, winreg.REG_DWORD, 0)
                winreg.SetValueEx(key, 'CloseOnExit', 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, 'NemoRenderer', 0, winreg.REG_DWORD,
                                 {'gdi':0,'opengl':1,'directx':2}[renderer])
            with tempfile.TemporaryDirectory(prefix='nemoterm-shutdown-') as tmp, OwnedJob() as job:
                events, session = [], None
                case = dict(renderer=renderer, close=close, observer=observer,
                            injected=observer != 'none', events=events)
                evidence['cases'].append(case)
                checkpoint(case, 'spawn')
                report, control = Path(tmp)/'report', Path(tmp)/'control'
                process = job.spawn([str(exe), '-load', profile, '--cols', '40', '--rows', '12',
                    '-e', sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control)],
                    env=dict(os.environ, NEMOTERM_CONPTY='bundled'), creationflags=subprocess.CREATE_NO_WINDOW)
                case['pid'] = process.pid
                try:
                    checkpoint(case, 'window-ready')
                    hwnd = wait_for(lambda: find_window(process.pid))
                    checkpoint(case, 'fixture-ready')
                    wait_for(lambda: read_snapshot(report))
                    case['active_renderer'] = int(u.GetPropW(hwnd, 'NemotermRenderer') or 0)
                    assert case['active_renderer'] in (1, 2, 3), case
                    if renderer == 'directx' and os.environ.get('NEMOTERM_REQUIRE_DIRECTX') == '1':
                        assert case['active_renderer'] == 3, case
                    if observer != 'none':
                        checkpoint(case, 'frida-attach')
                        session = frida.attach(process.pid)
                    if observer == 'lifetime':
                        checkpoint(case, 'frida-create-script')
                        script = session.create_script((root/'tests/shutdown_probe.js').read_text(encoding='utf-8'))
                        def on_message(message, data):
                            event = message['payload'] if message['type'] == 'send' else message
                            events.append(event)
                            print('Shutdown event:', json.dumps(event), flush=True)
                        script.on('message', on_message)
                        checkpoint(case, 'frida-load-script')
                        script.load()
                        checkpoint(case, 'frida-watch-window')
                        script.exports_sync.watch(hex(hwnd))
                    checkpoint(case, 'request-close')
                    if close == 'child-exit':
                        write_snapshot(control, dict(stop=True))
                    else:
                        owner = w.DWORD()
                        thread = u.GetWindowThreadProcessId(hwnd, c.byref(owner))
                        case['close_request'] = dict(hwnd=hwnd, thread=thread, pid=owner.value)
                        assert thread and owner.value == process.pid, case
                        case['close_request']['posted'] = bool(u.PostMessageW(hwnd, 0x10, 0, 0))
                        assert case['close_request']['posted'], case
                    checkpoint(case, 'wait-process-exit')
                    case['exit_code'] = process.wait(timeout=10)
                    assert case['exit_code'] == 0, case
                    if observer == 'lifetime':
                        checkpoint(case, 'wait-shutdown-events')
                        wait_for(lambda: any(e.get('event') == 'com-uninitialize-return' for e in events))
                        freed = [e for e in events if e.get('event') == 'seat-free']
                        com = [e for e in events if e.get('event') == 'com-uninitialize']
                        returned = [e for e in events if e.get('event') == 'com-uninitialize-return']
                        assert freed and all(e['success'] and not e['window_alive'] for e in freed), case
                        assert com and all(not e['window_alive'] and e['seat_freed'] for e in com), case
                        assert returned and all(not e['window_alive'] and e['seat_freed'] and
                            sorted(e['detached_observers']) == ['com','heap','window'] for e in returned), case
                        assert not any(e.get('event') == 'callback-after-seat-free' for e in events), case
                        assert not any(e.get('type') == 'error' for e in events), case
                    checkpoint(case, 'assertions-passed')
                except BaseException as error:
                    case['error'] = repr(error)
                    case['failed_phase'] = case['phase']
                    record_owned_failure(process, job, case, 'shutdown-'+case['failed_phase'])
                    if args.failure_dump and process.poll() is None:
                        try:
                            from native_failure_dump import capture_owned_failure_dump
                            case['failure_dump'] = capture_owned_failure_dump(args.failure_dump,
                                process, job, root/'research'/('shutdown-failure-'+uuid.uuid4().hex))
                        except Exception as capture_error:
                            case['failure_dump_error'] = repr(capture_error)
                    case['child_report'] = read_snapshot(report)
                    write_snapshot(evidence_path, evidence)
                    raise
                finally:
                    primary_failure = sys.exc_info()[0] is not None
                    try:
                        if session:
                            checkpoint(case, 'frida-detach')
                            detach_session(session)
                    except Exception as error:
                        case['observer_cleanup_error'] = repr(error)
                        if not primary_failure:
                            raise
                    finally:
                        checkpoint(case, 'drain-owned-job')
                        case['cleanup'] = job.finish(grace=0 if primary_failure else 5)
                        process.wait(timeout=5)
                        checkpoint(case, 'cleanup-complete')
                    if not primary_failure:
                        assert not case['cleanup']['terminated_remaining'], case['cleanup']
    evidence['completed'] = True
finally:
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, keypath)
    finally:
        write_snapshot(evidence_path, evidence)
print('Native shutdown lifetime passed:', len(evidence['cases']), 'cases')
