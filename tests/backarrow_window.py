"""Replay four upstream Backspace profiles with real keys on a hosted Windows desktop."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from fixture_io import read_snapshot, write_snapshot
from hosted_gesture_input import DesktopInput
from native_test_utils import find_window, root, terminal_host, u, w, wait_for
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile

ACK = b'\x1b[0n'
# An unmodified printable key in the same SendInput stream proves every preceding
# key reached the input queue before the child asks for the second status reply.
SENTINEL = b'z'
VK = {'BackSpace': 0x08, 'Delete': 0x2e, 'Shift_L': 0x10, 'Control_L': 0x11}


def decode_reply(raw):
    # Keep the raw reply as the compatibility gate. Separately show whether
    # the reported mode and the decoded kbs value have the same meaning.
    match = re.fullmatch(rb'\x1b\[\?67;([0-4])\$y\x1bP1\+r6b6273=([A-Fa-f0-9]{2})\x1b\\', raw)
    return [int(match[1]), int(match[2], 16)] if match else None


def capture(exe, font, name, ref, result):
    profile, startup = name.split('-')
    assert ref['completed'] and ref['exit_code'] == 0 and ref['profile'] == profile
    settings = dict(NemoRenderer=0, WarnOnClose=0, NemoWin32Input=0, NemoAllowGetTcap=1,
                    NemoTcapName='xterm-256color', BackspaceIsDelete=int(startup == 'del'))
    if profile == 'tcap':
        settings['LinuxFunctionKeys'] = 9
    result.update(settings=settings, steps=[])
    with tempfile.TemporaryDirectory() as temp, OwnedJob() as job, saved_profile(settings) as args:
        report, control = Path(temp)/'report', Path(temp)/'control'
        proc = job.spawn([str(exe), *args, '--tabs', '--font', font, '--cols', '80', '--rows', '24',
                          '-e', sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control), '240'],
                         env=dict(os.environ, NEMOTERM_CONPTY='bundled', NEMOTERM_TEST_WIDE_INPUT='1',
                                  NEMOTERM_TEST_INPUT_CP='65001', NEMOTERM_TEST_EXACT_OUTPUT='1'),
                         creationflags=subprocess.CREATE_NO_WINDOW)
        desktop = None
        def current():
            value = read_snapshot(report)
            assert proc.poll() is None and not value.get('error'), value
            return value
        try:
            hwnd = wait_for(lambda: find_window(proc.pid)); host = terminal_host(hwnd)
            assert host != hwnd
            u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND,w.LPCWSTR], w.HANDLE
            result['renderer'] = u.GetPropW(hwnd, 'NemotermRenderer'); assert result['renderer'] == 1
            desktop = DesktopInput(proc.pid, host, hwnd, result.setdefault('desktop', {}))
            wait_for(lambda: (v := current()).get('columns') == 80 and v.get('rows') == 24)
            for step in ref['steps']:
                query, key, tail = bytes.fromhex(step['wire_with_barriers_hex']).split(ACK)
                assert not tail and (query+key).hex() == step['reply_hex']
                row = dict(label=step['label'], sequence_hex=step['sequence_hex'], actions=step['actions'],
                           expected_query=query.hex(), expected_key=key.hex())
                result['steps'].append(row)
                req = dict(phase=row['label'], sequence=bytes.fromhex(step['sequence_hex']).decode('ascii')+'\x1b[5n', preserve_mouse=True)
                write_snapshot(control, req)
                first = wait_for(lambda: v if (v:=current()).get('phase')==req['phase'] and bytes.fromhex(v['hex']).endswith(ACK) else None)
                prefix = bytes.fromhex(first['hex']); row['actual_query'] = prefix[:-len(ACK)].hex()
                for action, symbol, down in step['actions']:
                    assert action == 'key'
                    desktop.event(VK[symbol], bool(down), extended=symbol=='Delete')
                desktop.chord(ord('Z'))
                wait_for(lambda: (v:=current()).get('phase') == req['phase'] and bytes.fromhex(v['hex']).endswith(SENTINEL))
                write_snapshot(control, dict(req, input_barrier='after-key'))
                last = wait_for(lambda: v if (v:=current()).get('input_barrier')=='after-key' and v['phase']==req['phase'] else None)
                wire = bytes.fromhex(last['hex']); row['wire_with_sentinel_and_barriers_hex'] = wire.hex()
                assert wire.startswith(prefix) and wire.endswith(SENTINEL+ACK), row
                row['actual_key'] = wire[len(prefix):-len(SENTINEL+ACK)].hex()
                row['passed'] = row['actual_query']==row['expected_query'] and row['actual_key']==row['expected_key']
                row['query_fields'] = decode_reply(bytes.fromhex(row['actual_query']))
                row['expected_fields'] = decode_reply(query); assert row['expected_fields'] is not None
                row['same_key_and_fields'] = row['query_fields']==row['expected_fields'] and row['actual_key']==row['expected_key']
        finally:
            result['last_snapshot'] = read_snapshot(report)
            if desktop: desktop.restore()
            write_snapshot(control, dict(stop=True)); result['exit_code'] = proc.wait(timeout=10)
            result['cleanup'] = job.finish()
        assert result['exit_code']==0 and not result['cleanup']['terminated_remaining']


def main():
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted' and os.environ.get('GITHUB_ACTIONS')=='true'
    exe = Path(os.environ['NEMOTERM_TEST_EXE']).resolve(); font = os.environ['NEMOTERM_TEST_FONT']
    archive = root/'testdata/upstream/backarrow-xterm.zip'
    out = root/'research/backarrow-window.json'
    result = dict(completed=False, exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), font=font,
                  archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), fixture_commit=os.environ['GITHUB_SHA'], cases={})
    with zipfile.ZipFile(archive) as z:
        ref = json.loads(z.read('backarrow.json'))
        result['xterm_commit'] = z.read('upstream-commit.txt').decode().strip()
        result['xterm_sha256'] = ref['executable_sha256']
        assert z.read('executable-sha256.txt').decode().split()[0] == result['xterm_sha256']
    assert ref['completed'] and set(ref['cases']) == {'default-del','default-bs','tcap-del','tcap-bs'}
    try:
        for name, case in ref['cases'].items():
            row = result['cases'][name] = {}
            capture(exe, font, name, case, row)
        result['completed'] = True
        failed = [f"{name}/{s['label']}" for name,r in result['cases'].items() for s in r['steps'] if not s['passed']]
        result['mismatches'] = failed
        assert not failed, failed
    finally:
        out.write_text(json.dumps(result, indent=2), encoding='utf-8')


if __name__=='__main__': main()
