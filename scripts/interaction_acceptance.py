"""Prepare and run Windows interaction acceptance on GitHub-hosted runners."""
from pathlib import Path
import argparse
import datetime
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
FONT = os.environ.get('NEMOTERM_TEST_FONT', 'SarasaTermSC Nerd Font Light')


def catalog():
    cases = []
    def add(name, group, script, args=(), effects='window', timeout=900):
        cases.append(dict(id=name, group=group, script=script, args=list(args),
                          effects=effects, timeout_seconds=timeout))
    for api in ('byte', 'wide'):
        add('input-'+api, 'input', 'input_method_window_smoke.py',
            ['--tabs', '--input-api', api, '--font', FONT, '--foreground'], 'foreground; IMM; synthetic DPI')
    add('bindings', 'selection', 'bindings_window_smoke.py', effects='clipboard; temporary saved bindings')
    for renderer, number, side in [('gdi', '0', 'top'), ('directx', '2', 'left')]:
        add('selection-'+renderer, 'selection', 'selection_window_smoke.py',
            ['--renderer', number, '--tabs', '--tab-side', side, '--font', FONT], 'clipboard; selection pixels')
        add('drop-'+renderer, 'clipboard', 'drop_window_smoke.py',
            ['--renderer', renderer, '--font', FONT], 'clipboard; file-drop messages; isolated shell parsing')
    for client in ('codex', 'opencode'):
        add('agent-image-'+client, 'agents', 'agent_clipboard_smoke.py',
            ['--client', client, '--client-exe', '{'+client+'}', '--font', FONT], 'clipboard; isolated real client; loopback provider')
    add('agent-selection-roundtrip', 'agents', 'codex_window_smoke.py',
        ['--codex', '{codex}', '--tabs', '--paste-selection', '--font', FONT],
        'clipboard; isolated real Codex; selected response submitted to loopback provider')
    add('agent-selection-directx', 'agents', 'codex_window_smoke.py',
        ['--codex', '{codex}', '--tabs', '--paste-selection', '--renderer', 'directx', '--font', FONT],
        'clipboard; isolated real Codex; DirectX; selected Unicode submitted to loopback provider')
    for renderer in ('gdi','directx'):
        add('opencode-selection-'+renderer, 'agents', 'opencode_selection_smoke.py',
            ['--client-exe', '{opencode}', '--font', FONT, '--renderer', renderer],
            'clipboard; isolated real OpenCode; mouse tracking; selected Unicode submitted to loopback provider')
    add('unicode-presented-gdi', 'rendering', 'kitty_unicode_window_smoke.py',
        ['--renderer', 'gdi', '--presented-gdi'], 'foreground; presented pixel capture')
    add('renderers', 'rendering', 'renderer_window_smoke.py')
    add('font-zoom', 'rendering', 'font_zoom_window_smoke.py')
    add('mouse-wire', 'mouse', 'mouse_window_smoke.py', effects='owned mouse messages; no physical input')
    add('mouse-colours', 'mouse', 'pointer_window_smoke.py',
        ['--colour-reference', 'tests/pointer-colour-resets-reference.zip', '--font', FONT],
        'owned foreground; actual OS cursor inks, XTerm replies and hidden tabs')
    for renderer, side in [('gdi', 'top'), ('gdi', 'bottom'), ('directx', 'left'), ('opengl', 'right')]:
        add('tabs-'+side, 'tabs', 'tabs_window_smoke.py',
            ['--renderer', renderer, '--side', side, '--font', FONT, '--cols', '160', '--rows', '48', '--session-seconds', '900'])
        add('resize-'+side, 'tabs', 'window_resize_window_smoke.py', ['--tabs', '--tab-side', side])
    add('settings', 'settings', 'settings_window_smoke.ps1', effects='native dialog; temporary saved profile')
    add('settings-tabs', 'settings', 'settings_window_smoke.ps1', ['-TabHost'], 'native dialog; temporary saved profile')
    add('shells', 'shells', 'shell_window_smoke.py', effects='available local shells; isolated fixture commands')
    add('bell-api', 'bell', 'bell_window_smoke.py', effects='system sound')
    add('bell-visual', 'bell', 'bell_visual_window_smoke.py', effects='visual flash')
    workloads = [('text', []), ('inline', ['--inline-images']),
        ('animated', ['--animated-images']), ('kitty', ['--kitty-images']),
        ('compressed-kitty', ['--kitty-images', '--kitty-compression']),
        ('unicode-kitty', ['--kitty-images', '--kitty-unicode'])]
    for renderer, side in [('gdi', 'top'), ('directx', 'left')]:
        for name, image_args in workloads:
            add('full-grid-'+name+'-'+renderer, 'memory-'+renderer, 'tabs_window_smoke.py',
                ['--renderer', renderer, '--side', side, '--font', FONT,
                 '--cols', '160', '--rows', '48', '--require-grid', '--session-seconds', '900',
                 '--workload-memory']+image_args,
                'full Sarasa grid; uninjected memory sampling; image pixels; tab lifetime')
    return cases


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, value):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def files(folder):
    return {p.relative_to(folder).as_posix(): digest(p) for p in sorted(folder.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def selected(cases, groups=(), names=()):
    unknown = set(groups)-{c['group'] for c in cases}
    unknown |= set(names)-{c['id'] for c in cases}
    if unknown:
        raise ValueError('Unknown selection: '+', '.join(sorted(unknown)))
    return [c for c in cases if (not groups and not names) or c['group'] in groups or c['id'] in names]


def require_remote_runner():
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise ValueError('Execution requires a disposable GitHub-hosted runner')


def desktop_ready():
    """Read-only check: caller must still reserve the desktop for the test."""
    if os.name != 'nt':
        raise RuntimeError('Execution requires Windows; plan/prepare are noninteractive')
    import ctypes as c
    user = c.WinDLL('user32', use_last_error=True)
    user.OpenInputDesktop.argtypes = [c.c_ulong, c.c_bool, c.c_ulong]
    user.OpenInputDesktop.restype = c.c_void_p
    user.GetUserObjectInformationW.argtypes = [c.c_void_p, c.c_int, c.c_void_p, c.c_ulong, c.POINTER(c.c_ulong)]
    user.CloseDesktop.argtypes = [c.c_void_p]
    handle = user.OpenInputDesktop(0, False, 1)  # DESKTOP_READOBJECTS
    if not handle:
        raise RuntimeError('Input desktop unavailable/locked; no test started')
    try:
        name = c.create_unicode_buffer(256); needed = c.c_ulong()
        if not user.GetUserObjectInformationW(handle, 2, name, c.sizeof(name), c.byref(needed)) or name.value.lower() != 'default':
            raise RuntimeError('Input desktop unavailable/locked; no test started')
    finally:
        user.CloseDesktop(handle)
    user.GetForegroundWindow.restype = c.c_void_p
    user.GetWindowThreadProcessId.argtypes = [c.c_void_p, c.POINTER(c.c_ulong)]
    pid = c.c_ulong(); window = user.GetForegroundWindow()
    if not window and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted':
        return  # A fresh hosted desktop can have no foreground window yet.
    if not window or not user.GetWindowThreadProcessId(window, c.byref(pid)):
        raise RuntimeError('Cannot identify foreground desktop')
    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [c.c_ulong, c.c_bool, c.c_ulong]
    kernel.OpenProcess.restype = c.c_void_p
    kernel.QueryFullProcessImageNameW.argtypes = [c.c_void_p, c.c_ulong, c.c_wchar_p, c.POINTER(c.c_ulong)]
    kernel.CloseHandle.argtypes = [c.c_void_p]
    process = kernel.OpenProcess(0x1000, False, pid.value)
    if not process: raise RuntimeError('Cannot inspect foreground process')
    try:
        path = c.create_unicode_buffer(32768); length = c.c_ulong(len(path))
        if not kernel.QueryFullProcessImageNameW(process, 0, path, c.byref(length)):
            raise RuntimeError('Cannot inspect foreground process')
        if Path(path.value).name.lower() in ('lockapp.exe', 'logonui.exe'):
            raise RuntimeError('Desktop is locked; no test started')
    finally:
        kernel.CloseHandle(process)


def prepare(args):
    stage = args.stage.resolve()
    if stage.exists():
        raise ValueError('Use a fresh stage; previous evidence is never replaced')
    exe = args.exe.resolve(strict=True)
    if digest(exe) != args.sha256.lower():
        raise ValueError('Executable SHA-256 differs from the reviewed candidate')
    stage.mkdir(parents=True)
    snapshot = stage/'snapshot'
    for name in ('tests', 'tools', 'research', 'dist'):
        (snapshot/name).mkdir(parents=True)
    for source in (ROOT/'tests').rglob('*'):
        if source.is_file() and '__pycache__' not in source.parts and source.suffix != '.pyc':
            target = snapshot/'tests'/source.relative_to(ROOT/'tests')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    shutil.copy2(ROOT/'research/pointer-colour-resets-reference.zip', snapshot/'tests')
    shutil.copy2(ROOT/'tools/nemoterm_debug.py', snapshot/'tools/nemoterm_debug.py')
    shutil.copy2(exe, snapshot/'dist/nemoterm.exe')
    shutil.copy2(__file__, stage/'runner.py')
    shutil.copy2(ROOT/'scripts/interaction_manual.py', stage/'interaction_manual.py')
    # The manual launcher imports this exact module beside itself.
    shutil.copy2(__file__, stage/'interaction_acceptance.py')
    clients = {}
    for name in ('codex', 'opencode'):
        path = getattr(args, name)
        if path:
            path = path.resolve(strict=True)
            clients[name] = dict(path=str(path), sha256=digest(path))
    identity = dict(executable_sha256=digest(exe), executable_bytes=exe.stat().st_size,
        executable_source=str(exe), font=FONT, clients=clients,
        fixture_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        fixture_dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
        snapshot_hashes=files(snapshot), runner_sha256=digest(stage/'runner.py'),
        helper_hashes={name: digest(stage/name) for name in ('interaction_manual.py', 'interaction_acceptance.py')})
    save(stage/'identity.json', identity)
    save(stage/'plan.json', catalog())
    save(stage/'results.json', [])
    save(stage/'manual-results.json', dict(status='not_run', executable_sha256=digest(exe),
        checks=[dict(id=i, status='not_run', evidence=[], notes='') for i in
                ('M01-startup', 'M02-copy-paste', 'M03-mouse-override', 'M04-rectangle',
                 'M05-drop', 'M06-tabs-preview', 'M07-resize', 'M08-ime-dpi',
                 'M09-zoom', 'M10-bell', 'M11-settings-shells', 'M12-real-agents')]))
    print('Prepared without launching any executable:', stage)


def verify_stage(stage):
    identity = load(stage/'identity.json')
    if files(stage/'snapshot') != identity['snapshot_hashes']:
        raise ValueError('Snapshot changed; create a fresh stage')
    if digest(stage/'runner.py') != identity['runner_sha256']:
        raise ValueError('Saved runner changed; create a fresh stage')
    for name, expected in identity['helper_hashes'].items():
        if digest(stage/name) != expected:
            raise ValueError('Saved helper changed: '+name)
    if load(stage/'plan.json') != catalog():
        raise ValueError('Plan differs; run the saved runner or prepare a fresh stage')
    return identity


def run(args):
    require_remote_runner()
    stage = args.stage.resolve(strict=True)
    identity = verify_stage(stage)
    cases = selected(load(stage/'plan.json'), args.group, args.case)
    # OS lock releases when the runner exits; an old file alone is not a live lock.
    import msvcrt
    with (stage/'run.lock').open('a+b') as lock:
        lock.seek(0); lock.write(b'0'); lock.flush(); lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        results = load(stage/'results.json')
        if any(r['status'] == 'running' for r in results):
            raise RuntimeError('Unfinished attempt: inspect its recorded process before using a fresh stage')
        if importlib.metadata.version('frida') != '17.24.3':
            raise RuntimeError('Expected Frida 17.24.3')
        importlib.metadata.version('Pillow')
        sys.path.insert(0, str(stage/'snapshot/tests'))
        from owned_job import OwnedJob
        for case in cases:
            if (stage/'STOP').exists():
                print('Stop requested; no next case started'); return 2
            history = [r for r in results if r['id'] == case['id']]
            if history and history[-1]['status'] == 'passed':
                prior = history[-1]
                for name, expected in prior['evidence'].items():
                    if digest(stage/prior['directory']/name) != expected:
                        raise ValueError('Prior passed evidence changed: '+name)
                print('Already passed:', case['id']); continue
            if history and not args.retry_failed:
                raise ValueError('Review previous failure; --retry-failed creates a new attempt')
            command_args = []
            for value in case['args']:
                if value.startswith('{'):
                    client = identity['clients'].get(value[1:-1])
                    if not client or digest(Path(client['path'])) != client['sha256']:
                        raise ValueError('Missing/changed client '+value+'; prepare a fresh stage')
                    value = client['path']
                command_args.append(value)
            desktop_ready()
            attempt = stage/'attempts'/f"{case['id']}-{len(history)+1:02d}"
            shutil.copytree(stage/'snapshot', attempt)
            (attempt/'build').mkdir()
            command = ([sys.executable] if case['script'].endswith('.py') else
                       ['powershell.exe', '-NoProfile', '-File'])
            command += ['tests/'+case['script'], *command_args]
            env = dict(os.environ, NEMOTERM_TEST_EXE=str(attempt/'dist/nemoterm.exe'),
                       NEMOTERM_TEST_FONT=identity['font'], NEMOTERM_REQUIRE_DIRECTX='1',
                       NEMOTERM_TEST_TRACEBACK_SECONDS='60')
            if case['script'].endswith('.ps1'):
                # The controller is started by pwsh; Windows PowerShell must
                # rebuild its own module search path for Get-FileHash, etc.
                env = {k: v for k, v in env.items() if k.upper() != 'PSMODULEPATH'}
            row = dict(id=case['id'], status='running', directory=attempt.relative_to(stage).as_posix(),
                       command=command, started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
            results.append(row); save(stage/'results.json', results)
            started = time.monotonic()
            print('Starting:', case['id'], flush=True)
            with (attempt/'output.log').open('w', encoding='utf-8') as output, OwnedJob() as job:
                try:
                    process = job.spawn(command, cwd=attempt, env=env, stdout=output,
                                        stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
                    row['pid'] = process.pid; save(stage/'results.json', results)
                    row['exit_code'] = process.wait(timeout=case['timeout_seconds'])
                    row['status'] = 'passed' if row['exit_code'] == 0 else 'failed'
                except KeyboardInterrupt:
                    row.update(status='interrupted', error='Controller interrupted; inspect clipboard restoration')
                except Exception as exc:
                    row.update(status='failed', error=repr(exc))
                finally:
                    try:
                        failure_observer = None
                        if os.environ.get('NEMOTERM_JOB_FAILURE_CAPTURE') == '1':
                            from job_failure_snapshot import capture_job_failure
                            failure_observer = lambda owned, handles: capture_job_failure(
                                owned, handles, attempt/'research/job-failure',
                                os.environ.get('NEMOTERM_JOB_FAILURE_DUMP'))
                        row['cleanup'] = job.finish(grace=3, observe_after_deadline=
                            float(os.environ.get('NEMOTERM_JOB_FAILURE_OBSERVE_SECONDS', '0')),
                            failure_observer=failure_observer)
                    except Exception as exc:
                        row.update(status='failed', cleanup_error=repr(exc))
                    if row.get('cleanup', {}).get('terminated_remaining'):
                        row['status'] = 'failed'
                        row['forced_cleanup'] = 'Only this job was stopped; clipboard restoration may be incomplete'
                    if row.get('cleanup', {}).get('grace_exceeded'):
                        row['status'] = 'failed'
                        row['deadline_exceeded'] = 'Late natural exit remains a failed acceptance'
                    if digest(attempt/'dist/nemoterm.exe') != identity['executable_sha256']:
                        row.update(status='failed', image_changed=True)
                    row['seconds'] = time.monotonic()-started
                    row['evidence'] = {'output.log': digest(attempt/'output.log')}
                    for folder in ('research', 'build'):
                        row['evidence'].update({folder+'/'+name: value for name, value in files(attempt/folder).items()})
                    save(stage/'results.json', results)
            print(case['id'], row['status'], flush=True)
            print((attempt/'output.log').read_text(encoding='utf-8', errors='replace'), flush=True)
            if row['status'] != 'passed':
                if not args.continue_on_failure:
                    return 1
    failed = [c['id'] for c in cases if next(r for r in reversed(results) if r['id'] == c['id'])['status'] != 'passed']
    print('Failed checks:', failed)
    return int(bool(failed))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action')
    sub.add_parser('plan')
    p = sub.add_parser('prepare')
    p.add_argument('--stage', type=Path, required=True)
    p.add_argument('--exe', type=Path, required=True)
    p.add_argument('--sha256', required=True)
    p.add_argument('--codex', type=Path)
    p.add_argument('--opencode', type=Path)
    p = sub.add_parser('run')
    p.add_argument('--stage', type=Path, required=True)
    p.add_argument('--group', action='append', default=[])
    p.add_argument('--case', action='append', default=[])
    p.add_argument('--continue-on-failure', action='store_true')
    p.add_argument('--retry-failed', action='store_true')
    for command in ('status', 'stop'):
        p = sub.add_parser(command); p.add_argument('--stage', type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.action or args.action == 'plan':
        print(json.dumps(catalog(), ensure_ascii=False, indent=2))
    elif args.action == 'prepare':
        prepare(args)
    elif args.action == 'run':
        return run(args)
    elif args.action == 'stop':
        args.stage.resolve(strict=True).joinpath('STOP').touch()
        print('Stop requested after the current case; current input/clipboard activity may continue until it exits.')
    else:
        print(json.dumps(load(args.stage/'results.json'), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
