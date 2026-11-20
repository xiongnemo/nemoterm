"""Compare a Windows application's ReadConsoleOutputW and cursor with frontend VT replies.

Use printable ASCII so a disagreement cannot be caused by differing wide-cell
encodings. The session is owned by the hosted Windows job only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from native_test_utils import c, u, w
import time
import zipfile

from column_mode_saved_cases import AWAY, BLANK, C, HOME, MARK, PAINT, QUERY, saved_cases
from protocol_oracle_window import root, run

def replies(wire):
    cursor = re.match(rb'\x1b\[(\d+);(\d+)R\x1b\[8;(\d+);(\d+)t', wire)
    assert cursor, wire.hex()
    tail = wire[cursor.end():]
    groups = re.findall(rb'\x1bP([3-6])!~([0-9A-F]{4})\x1b\\', tail)
    assert [k for k, _ in groups] == [b'3', b'4', b'5', b'6'] and b''.join(
        b'\x1bP'+k+b'!~'+v+b'\x1b\\' for k,v in groups) == tail, tail.hex()
    return dict(size=[int(cursor[4]), int(cursor[3])], cursor=[int(cursor[2])-1, int(cursor[1])-1],
                text=''.join(chr(int(v, 16)) for _,v in groups))


def ordinary_cases(policy, allow):
    cases = [('baseline', C+'?40;95h'+PAINT, 80, AWAY, MARK),
             ('widen-keep', C+'?3h', 132 if allow else 80, HOME if allow else AWAY, MARK),
             ('narrow-keep', PAINT+C+'?3l', 80, HOME if allow else AWAY, MARK),
             ('same-width-clear', PAINT+C+'?95l'+C+'?3l', 80, HOME if allow else AWAY, BLANK if allow else MARK),
             ('disabled-by-app', C+'?40l'+PAINT+C+'?3h', 80, AWAY, MARK),
             ('reenable-clear', C+'?40h'+C+'?3h', 132 if allow else 80, HOME if allow else AWAY, BLANK if allow else MARK)]
    # A separate client starts with the profile switch off; without any
    # preceding ?40, the host has only the actual launch policy to consult.
    cases[:0] = [('startup-default', PAINT+C+'?3h', 132 if allow else 80,
                  HOME if allow else AWAY, BLANK if allow else MARK),
                 ('return-to-80', C+'?3l', 80, HOME if allow else AWAY, BLANK if allow else MARK)]
    if policy == 'startup-off':
        cases = [('deny-at-start', PAINT+C+'?3h',80,AWAY,MARK),
                 ('enable-at-runtime', C+'?40;95h'+C+'?3h',132,HOME,MARK)]
    if policy == 'allow':
        cases += [('reset-before-dialog', C+'?3l',80,HOME,BLANK),
                  ('live-deny', PAINT+C+'?3h',80,AWAY,MARK),
                  ('live-allow', C+'?95h'+C+'?3h',132,HOME,MARK),
                  ('in-order', PAINT+C+'?3l'+C+'2;4H!'+C+'7;11H',80,AWAY,'K!EP')]
    return cases


def main(saved):
    if os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise RuntimeError('GitHub-hosted desktop required')
    gpu = os.environ['RENDERER']
    name = ('column-mode-saved-readback-' if saved else 'column-mode-readback-') + gpu
    records = dict(sha256=hashlib.sha256(Path(os.environ['NEMOTERM_TEST_EXE']).read_bytes()).hexdigest(),
                   api=['ReadConsoleOutputW', 'GetConsoleScreenBufferInfo'], profiles={})
    for policy in (('allow', 'deny', 'startup-off', 'auto') if saved else ('allow', 'deny', 'startup-off')):
        allow = policy != 'deny'
        output = records['profiles'][policy] = {}
        if not saved:
            cases = [(k, cmd, dict(size=[cols,24],cursor=list(pos),text=text), None)
                     for k,cmd,cols,pos,text in ordinary_cases(policy,allow)]
        elif not allow:
            # All directives that would change width are denied. Only the
            # final input explicitly overwrites KEEP and homes the cursor.
            cases = [(k, cmd, dict(size=[80,24],cursor=list(HOME if k=='restore-preserves-margins' else AWAY),
                                   text='GOOD' if k=='restore-preserves-margins' else MARK), None)
                     for k,cmd in saved_cases().items()]
        else:
            source = root/'testdata/upstream/xterm412-saved-column-modes.zip'
            records['reference_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
            with zipfile.ZipFile(source) as archive:
                option = {'allow':'on','startup-off':'off','auto':'auto'}[policy]
                captured = json.loads(archive.read('column-modes/saved-'+option+'.json'))
                records['xterm_sha256'] = archive.read('executable-sha256.txt').decode().split()[0]
            assert captured['version']=='XTerm(412)' and captured['executable_sha256']==records['xterm_sha256']
            reference, inputs = captured['cases'], saved_cases()
            assert list(reference) == list(inputs)
            cases = []
            for key,command in inputs.items():
                assert reference[key]['sequence'] == command+QUERY, key
                wire = bytes.fromhex(reference[key]['reply_hex'])
                cases.append((key, command, replies(wire), wire))

        def exercise(hwnd, phase, current):
            for key, command, expected, reference_bytes in cases:
                if key in ('live-deny','live-allow'):
                    pid = w.DWORD()
                    assert u.GetWindowThreadProcessId(hwnd,c.byref(pid)) and pid.value
                    ui = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
                        '-File',str(root/'tests/owned_profile_settings.ps1'),'-TargetProcess',str(pid.value),
                        '-TargetWindow',str(hwnd),'-Action',key.replace('live-','resize-')],capture_output=True,timeout=65)
                    records.setdefault('live_settings',{})[key] = dict(pid=pid.value,hwnd=hwnd,exit_code=ui.returncode,
                        log=(ui.stdout+ui.stderr).decode('utf8',errors='replace'))
                    ui.check_returncode()
                raw = phase(key, command+QUERY, None)
                front = replies(raw)
                def read():
                    state = current()
                    assert state['phase'] == key and len(state['native_row']) == 4
                    return dict(size=[state['columns'],state['rows']],cursor=state['screen_cursor'],
                                text=''.join(chr(pair[0]) for pair in state['native_row']),cells=state['native_row'])
                def matches(sample): return all(sample[k] == v for k,v in expected.items())
                first = sample = read()
                end = time.monotonic()+1
                while not matches(sample) and time.monotonic()<end:
                    time.sleep(.04); sample = read()
                output[key] = dict(expected=expected, input=command.encode().hex(), wire=raw.hex(),reference_wire=reference_bytes.hex() if reference_bytes is not None else None,
                                   frontend=front, first=first,settled=sample,
                                   passed=((reference_bytes is None or raw==reference_bytes) and front==expected and matches(sample) and ((allow and key not in ('live-deny','deny-at-start')) or matches(first))))
            return output

        try:
            run(name+'-'+policy, [], exercise=exercise, barrier=(C+'5n',b'\x1b[0n'),
                native_row=(2,1,4), font=os.environ['NEMOTERM_TEST_FONT'],
                source_reference='XTerm(412)' if saved and allow else 'Windows console and local profile policy',
                profile=dict(NemoTabs=1,NemoRenderer={'gdi':0,'directx':2}[gpu],NemoColumnModeStart={'startup-off':2,'auto':0}.get(policy,1),
                             NoRemoteResize=int(not allow),NemoAllowChecksum=1,FontHeight=8,WarnOnClose=0))
        finally:
            (root/'research'/(name+'-results.json')).write_text(json.dumps(records,indent=2),encoding='utf8')
    missing=[(policy,key) for policy,rows in records['profiles'].items() for key,row in rows.items() if not row['passed']]
    assert not missing, missing


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--saved', action='store_true')
    main(parser.parse_args().saved)
