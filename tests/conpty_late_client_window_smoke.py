"""Resume an inherited console client only after its terminal was closed."""
import argparse
import uuid
import winreg
from native_test_utils import (root, c, w, k, u, os, sys, subprocess, Path,
    tempfile, time, hashlib, read_snapshot, write_snapshot, wait_for, find_window)
from owned_job import OwnedJob, k
from job_failure_snapshot import capture_job_failure

if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
    raise RuntimeError('This lifecycle test requires a disposable GitHub-hosted runner')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--helper', type=Path, required=True)
args = parser.parse_args()
helper = args.helper.resolve(strict=True)
exe = Path(os.environ['NEMOTERM_TEST_EXE']).resolve(strict=True)
k.OpenThread.argtypes, k.OpenThread.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
k.GetProcessIdOfThread.argtypes, k.GetProcessIdOfThread.restype = [w.HANDLE], w.DWORD
k.ResumeThread.argtypes, k.ResumeThread.restype = [w.HANDLE], w.DWORD
u.PostMessageW.argtypes, u.PostMessageW.restype = [w.HWND, w.UINT, w.WPARAM, w.LPARAM], w.BOOL
profile = 'late-console-'+uuid.uuid4().hex
keypath = 'Software\\Nemo\\Nemoterm\\Sessions\\'+profile
evidence = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    helper_sha256=hashlib.sha256(helper.read_bytes()).hexdigest(), completed=False, cases=[])
output = root/'research/conpty-late-client-observed.json'
try:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, keypath) as key:
        winreg.SetValueEx(key, 'WarnOnClose', 0, winreg.REG_DWORD, 0)
    for iteration, mode in enumerate(['before-close']*2 + ['after-parent-exit']*4):
        case = dict(iteration=iteration+1, mode=mode, passed=False); evidence['cases'].append(case)
        with tempfile.TemporaryDirectory(prefix='nemoterm-late-client-') as temporary, OwnedJob() as job:
            report = Path(temporary)/'parent.json'
            process = job.spawn([str(exe), '--no-tabs', '-load', profile, '-e',
                str(helper), 'parent', str(report)], env=dict(os.environ, NEMOTERM_CONPTY='bundled'),
                creationflags=subprocess.CREATE_NO_WINDOW)
            parent = child = thread = None
            try:
                hwnd = wait_for(lambda: find_window(process.pid))
                info = wait_for(lambda: read_snapshot(report), timeout=15)
                case['clients'] = info
                parent = k.OpenProcess(0x101000, False, info['parent'])
                child = k.OpenProcess(0x101000, False, info['child'])
                thread = k.OpenThread(0x100042, False, info['thread'])
                assert parent and child and thread
                for handle in (parent, child):
                    member = w.BOOL()
                    assert k.IsProcessInJob(handle, job.handle, c.byref(member)) and member.value
                assert k.GetProcessIdOfThread(thread) == info['child']
                if mode == 'before-close':
                    case['previous_suspend_count'] = k.ResumeThread(thread)
                    assert case['previous_suspend_count'] == 1
                    case['child_before_close'] = wait_for(
                        lambda: read_snapshot(Path(str(report)+'-child')), timeout=10)
                    assert case['child_before_close']['connected'] >= 2
                    assert case['child_before_close']['phase'] == 'before-read'
                case['close_requested_filetime'] = time.time_ns()//100+116444736000000000
                assert u.PostMessageW(hwnd, 0x10, 0, 0)
                # The parent's exit witnesses delivery of the close request.
                # A suspended inherited client can itself delay frontend
                # teardown; waiting for that teardown before resuming it
                # prevents this control from reaching the intended boundary.
                assert k.WaitForSingleObject(parent, 10000) == 0
                case['parent_exit_observed_filetime'] = time.time_ns()//100+116444736000000000
                case['frontend_exit_before_resume'] = process.poll()
                if mode == 'after-parent-exit':
                    assert k.WaitForSingleObject(child, 0) == 258
                    case['resume_filetime'] = time.time_ns()//100+116444736000000000
                    case['previous_suspend_count'] = k.ResumeThread(thread)
                    assert case['previous_suspend_count'] == 1
                case['frontend_exit'] = process.wait(timeout=10)
                assert case['frontend_exit'] == 0
                case['cleanup'] = job.finish(grace=3, observe_after_deadline=12,
                    failure_observer=lambda owned, handles: capture_job_failure(owned, handles,
                        root/'research'/f'late-client-failure-{iteration+1}',
                        os.environ.get('NEMOTERM_JOB_FAILURE_DUMP')))
                case['child_report'] = read_snapshot(Path(str(report)+'-child'))
                case['passed'] = not (case['cleanup']['grace_exceeded'] or
                                      case['cleanup']['terminated_remaining'])
            except Exception as error:
                case['error'] = repr(error)
                case['cleanup'] = job.finish(grace=0,
                    failure_observer=lambda owned, handles: capture_job_failure(owned, handles,
                        root/'research'/f'late-client-failure-{iteration+1}',
                        os.environ.get('NEMOTERM_JOB_FAILURE_DUMP')))
            finally:
                case['child_report'] = read_snapshot(Path(str(report)+'-child'))
                case.setdefault('cleanup', job.finish(grace=0))
                process.wait(timeout=5)
                for handle in (parent, child, thread):
                    if handle: k.CloseHandle(handle)
                write_snapshot(output, evidence)
            print('Late console client', iteration+1, case['passed'], flush=True)
    evidence['completed'] = True
finally:
    write_snapshot(output, evidence)
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, keypath)
raise SystemExit(0 if all(case['passed'] for case in evidence['cases']) else 1)
