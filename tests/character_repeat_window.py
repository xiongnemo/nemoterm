"""Check coalesced Win32 character messages at the child of one owned terminal."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from native_test_utils import find_window, read_snapshot, u, wait_for, write_snapshot
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile

ROOT = Path(__file__).resolve().parents[1]
ACK = b'\x1b[0n'
CHAR, SYSCHAR, UNICHAR, IME = 0x102, 0x106, 0x109, 0x286
CASES = [
    ('single', [(CHAR, 90, 1)], 'Z'),
    ('char', [(CHAR, 0x4e2d, 3)], '中' * 3),
    ('syschar', [(SYSCHAR, 65, 4)], 'AAAA'),
    ('ime-char', [(IME, 0x6587, 4)], '文' * 4),
    ('utf16-pairs', [(CHAR, 0xd83d, 3), (CHAR, 0xde42, 3)], '🙂' * 3),
    ('ime-pairs', [(IME, 0xd840, 2), (IME, 0xdc00, 2)], '𠀀' * 2),
    ('utf32', [(UNICHAR, 0x1f642, 5)], '🙂' * 5),
    ('orphan', [(CHAR, 0xd83d, 3), (CHAR, 66, 2), (CHAR, 0xde42, 1)], 'BB'),
    ('probe', [(UNICHAR, 0xffff, 9), (UNICHAR, 90, 0)], 'Z'),
]


def collect(exe, font, wide, result):
    api = 'ReadConsoleW' if wide else 'ReadFile'
    record = result['readers'][api] = {'cases': []}
    with tempfile.TemporaryDirectory() as tmp, OwnedJob() as job, saved_profile(
            dict(NemoRenderer=0, NemoWin32Input=0, WarnOnClose=0, CloseOnExit=1)) as profile:
        state, control = (Path(tmp)/f for f in ('state', 'control'))
        proc = job.spawn([str(exe), *profile, '--tabs', '--font', font, '-e', sys.executable,
                          str(ROOT/'tests/mouse_fixture.py'), str(state), str(control), '120'],
                         creationflags=subprocess.CREATE_NO_WINDOW,
                         env=dict(os.environ, NEMOTERM_CONPTY='bundled', NEMOTERM_TEST_UTF8_INPUT='1',
                                  NEMOTERM_TEST_WIDE_INPUT=str(int(wide))))
        try:
            hwnd = wait_for(lambda: find_window(proc.pid)); record['hwnd'] = hwnd
            for protocol in ('legacy', 'kitty'):
                mode = '\x1b[=31u' if protocol == 'kitty' else '\x1b[=0u'
                for name, messages, text in CASES:
                    label = protocol + '-' + name
                    request = dict(phase=label, sequence='\x1b[?9001l' + mode + '\x1b[5n')
                    write_snapshot(control, request)
                    def snapshot():
                        s = read_snapshot(state)
                        return s if s.get('phase') == label else {}
                    wait_for(lambda: snapshot().get('hex') == ACK.hex())
                    replies = [u.SendMessageW(hwnd, msg, ch, count) for msg, ch, count in messages]
                    write_snapshot(control, dict(request, input_barrier=label))
                    s = wait_for(lambda: v if (v := snapshot()).get('input_barrier') == label else None)
                    expected = (text.encode('utf-8') if protocol == 'legacy' else
                                ''.join(f'\x1b[0;1;{ord(ch)}u' for ch in text).encode('ascii'))
                    actual = bytes.fromhex(s['hex'])
                    record['cases'].append(dict(name=label, messages=messages, replies=replies,
                        expected_hex=(ACK+expected+ACK).hex(), actual_hex=actual.hex(),
                        passed=actual == ACK+expected+ACK and s['input_api'] == api and s['input_cp'] == 65001
                               and (name != 'probe' or replies[0] == 1)))
        finally:
            write_snapshot(control, dict(stop=True))
            record['exit_code'] = proc.wait(timeout=10)
            record['cleanup'] = job.finish()


if __name__ == '__main__':
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise RuntimeError('GitHub-hosted Windows runner required')
    exe = Path(os.environ['NEMOTERM_TEST_EXE']).resolve(); font = os.environ['NEMOTERM_TEST_FONT']
    result = dict(exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), font=font,
                  fixture_commit=os.environ['GITHUB_SHA'], readers={})
    try:
        for wide in (False, True): collect(exe, font, wide, result)
    finally:
        (ROOT/'research/backarrow-character-repeat.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    for api,record in result['readers'].items():
        print(api, sum(c['passed'] for c in record['cases']), '/', len(record['cases']))
    if any(len(r['cases']) != 2*len(CASES) or not all(c['passed'] for c in r['cases'])
           or r['exit_code'] != 0 or r['cleanup']['terminated_remaining'] for r in result['readers'].values()):
        raise SystemExit(1)
