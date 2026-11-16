"""Dedicated manual surface: display generated scenes and record input, never execute it."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from interaction_acceptance import FONT, desktop_ready, digest, load, save, verify_stage

RESET = '\x1b[?1049l\x1b[?9;1000;1002;1003;1006;2004l\x1b[0m\x1b[2J\x1b[H'
TEXT = '0123456789\r\nab中e\u0301FGHIJ\r\nklmnopqrst\r\n\r\nNEMOTERM_MANUAL_FIXTURE\r\n'
SCENES = {
    'text': RESET+TEXT,
    'mouse': RESET+TEXT+'\x1b[?1003;1006h',
    'alternate': RESET+'\x1b[?1049h\x1b[2J\x1b[H'+TEXT+'\x1b[?1003;1006h',
    'paste': RESET+TEXT+'\x1b[?2004h',
    'bell': RESET+TEXT+'\x07',
    'history': RESET+''.join(f'{i:04d} 文件 e\u0301 history\r\n' for i in range(300))+TEXT,
    'link': RESET+TEXT+'\x1b]8;;https://example.invalid/nemoterm\x1b\\LINK_TEST\x1b]8;;\x1b\\',
}


def active(stage):
    record = load(stage/'manual-active.json')
    directory = (stage/record['directory']).resolve(strict=True)
    if not directory.is_relative_to(stage/'manual'):
        raise ValueError('Invalid manual directory')
    return directory


def archive_report(directory):
    report = directory/'report.json'
    if report.exists():
        with (directory/'events.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(load(report), ensure_ascii=False)+'\n')


def start(args):
    if not args.desktop_ready:
        raise ValueError('Reserve the desktop, then supply --desktop-ready')
    stage = args.stage.resolve(strict=True)
    identity = verify_stage(stage)
    desktop_ready()
    import msvcrt
    with (stage/'run.lock').open('a+b') as lock:
        lock.seek(0); lock.write(b'0'); lock.flush(); lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        if (stage/'manual-active.json').exists():
            previous = active(stage)
            if not (previous/'result.json').exists():
                raise RuntimeError('Previous manual process has no exit record; inspect it before a fresh stage')
        number = len(list((stage/'manual').glob('attempt-*')))+1
        directory = stage/'manual'/f'attempt-{number:02d}'
        shutil.copytree(stage/'snapshot', directory)
        (directory/'build').mkdir()
        sys.path.insert(0, str(directory/'tests'))
        from owned_job import OwnedJob
        from protocol_oracle_window import saved_profile
        save(directory/'control.json', dict(phase='initial', sequence=SCENES['text']))
        env = dict(os.environ, NEMOTERM_CONPTY='bundled', NEMOTERM_TEST_UTF8_INPUT='1',
                   NEMOTERM_TEST_EXACT_OUTPUT='1')
        result = dict(executable_sha256=identity['executable_sha256'], renderer=args.renderer,
                      side=args.side, font=FONT, status='running', assertions='manual; no automated pass')
        save(stage/'manual-active.json', dict(directory=directory.relative_to(stage).as_posix()))
        with saved_profile(dict(WarnOnClose=0, NemoWin32Input=0,
                                NemoRenderer={'gdi': 0, 'opengl': 1, 'directx': 2}[args.renderer])) as profile, OwnedJob() as job:
            process = job.spawn([str(directory/'dist/nemoterm.exe'), *profile, '--automation',
                '--tabs', '--tab-side', args.side,
                '--cols', '160', '--rows', '48', '--font', FONT, '-e', sys.executable,
                str(directory/'tests/mouse_fixture.py'), str(directory/'report.json'),
                str(directory/'control.json'), '1800'], env=env, cwd=directory,
                creationflags=subprocess.CREATE_NO_WINDOW)
            result['pid'] = process.pid
            save(directory/'identity.json', result)
            print('Manual surface PID', process.pid, 'Record:', directory, flush=True)
            print('Use scene/show/stop in another console. Pasted text is recorded, never executed.', flush=True)
            started = time.monotonic()
            try:
                sys.path.insert(0, str(directory/'tools'))
                import nemoterm_debug as api
                deadline = time.monotonic()+20
                instance = None
                while time.monotonic() < deadline and process.poll() is None:
                    instance = next(iter(api.discover(process.pid)), None)
                    if instance: break
                    time.sleep(.1)
                if not instance:
                    raise RuntimeError('Manual terminal discovery failed')
                result['initial_sessions'] = instance['sessions']
                save(directory/'identity.json', result)
                while process.poll() is None and time.monotonic()-started < 1800:
                    if (directory/'STOP').exists():
                        save(directory/'control.json', dict(stop=True))
                        break
                    time.sleep(.2)
                process.wait(timeout=15)
                result.update(status='needs-review' if process.returncode == 0 else 'failed', exit_code=process.returncode)
            except KeyboardInterrupt:
                result['status'] = 'interrupted'
                save(directory/'control.json', dict(stop=True))
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: pass
            except Exception as exc:
                result.update(status='failed', error=repr(exc))
                raise
            finally:
                archive_report(directory)
                result['cleanup'] = job.finish()
                if result['cleanup']['terminated_remaining']:
                    result['status'] = 'interrupted'
                result['executable_unchanged'] = digest(directory/'dist/nemoterm.exe') == identity['executable_sha256']
                save(directory/'result.json', result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for name in ('start', 'scene', 'show', 'stop'):
        p = sub.add_parser(name); p.add_argument('--stage', type=Path, required=True)
        if name == 'start':
            p.add_argument('--desktop-ready', action='store_true')
            p.add_argument('--renderer', choices=('gdi', 'directx', 'opengl'), default='gdi')
            p.add_argument('--side', choices=('top', 'bottom', 'left', 'right'), default='top')
        if name == 'scene':
            p.add_argument('--name', choices=tuple(SCENES), required=True)
    args = parser.parse_args(argv)
    if args.action == 'start':
        return start(args)
    directory = active(args.stage.resolve(strict=True))
    if args.action == 'show':
        report = load(directory/'report.json')
        report['decoded_input'] = bytes.fromhex(report.get('hex', '')).decode('utf-8', errors='replace')
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.action == 'scene':
        desktop_ready()
        if (directory/'result.json').exists():
            raise ValueError('Manual session already ended')
        archive_report(directory)
        save(directory/'control.json', dict(phase=args.name+'-'+str(time.time_ns()), sequence=SCENES[args.name]))
    else:
        (directory/'STOP').touch()


if __name__ == '__main__':
    main()
