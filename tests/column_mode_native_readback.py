"""Compare a Windows application's ReadConsoleOutputW and cursor with frontend VT replies.

Use printable ASCII so a disagreement cannot be caused by differing wide-cell
encodings. The session is owned by the hosted Windows job only.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time

from column_mode_cases import C
from protocol_oracle_window import root, run

PAINT = C + '2;3HKEEP' + C + '7;11H'
QUERY = C + '6n' + C + '18t' + C + '31#y' + ''.join(
    C + f'{x};1;2;{x};2;{x}*y' for x in range(3, 7))
MARK = 'KEEP'
BLANK = '    '
HOME = (0, 0)
AWAY = (10, 6)


def replies(wire):
    cursor = re.match(rb'\x1b\[(\d+);(\d+)R\x1b\[8;(\d+);(\d+)t', wire)
    assert cursor, wire.hex()
    tail = wire[cursor.end():]
    groups = re.findall(rb'\x1bP([3-6])!~([0-9A-F]{4})\x1b\\', tail)
    assert [k for k, _ in groups] == [b'3', b'4', b'5', b'6'] and b''.join(
        b'\x1bP'+k+b'!~'+v+b'\x1b\\' for k,v in groups) == tail, tail.hex()
    return dict(size=[int(cursor[4]), int(cursor[3])], cursor=[int(cursor[2])-1, int(cursor[1])-1],
                text=''.join(chr(int(v, 16)) for _,v in groups))


def main():
    if os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise RuntimeError('GitHub-hosted desktop required')
    gpu = os.environ['RENDERER']
    name = 'column-mode-readback-' + gpu
    records = dict(sha256=hashlib.sha256(Path(os.environ['NEMOTERM_TEST_EXE']).read_bytes()).hexdigest(),
                   api=['ReadConsoleOutputW', 'GetConsoleScreenBufferInfo'], profiles={})
    for policy in ('allow', 'deny'):
        allow = policy == 'allow'
        cases = [('baseline', C+'?40;95h'+PAINT, 80, AWAY, MARK),
                 ('widen-keep', C+'?3h', 132 if allow else 80, HOME if allow else AWAY, MARK),
                 ('narrow-keep', PAINT+C+'?3l', 80, HOME if allow else AWAY, MARK),
                 ('same-width-clear', PAINT+C+'?95l'+C+'?3l', 80, HOME if allow else AWAY, BLANK if allow else MARK),
                 ('disabled-by-app', C+'?40l'+PAINT+C+'?3h', 80, AWAY, MARK),
                 ('reenable-clear', C+'?40h'+C+'?3h', 132 if allow else 80, HOME if allow else AWAY, BLANK if allow else MARK)]
        output = records['profiles'][policy] = {}

        def exercise(hwnd, phase, current):
            for key, command, cols, pos, text in cases:
                expected = dict(size=[cols,24],cursor=list(pos),text=text)
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
                output[key] = dict(expected=expected, wire=raw.hex(),frontend=front, first=first,settled=sample,
                                   passed=(front==expected and matches(sample) and (allow or matches(first))))
            return output

        try:
            run(name+'-'+policy, [], exercise=exercise, barrier=(C+'5n',b'\x1b[0n'),
                native_row=(2,1,4), font=os.environ['NEMOTERM_TEST_FONT'],
                profile=dict(NemoTabs=1,NemoRenderer={'gdi':0,'directx':2}[gpu],NemoColumnModeStart=1,
                             NoRemoteResize=int(not allow),NemoAllowChecksum=1,FontHeight=8,WarnOnClose=0))
        finally:
            (root/'research'/(name+'-results.json')).write_text(json.dumps(records,indent=2),encoding='utf8')
    missing=[(policy,key) for policy,rows in records['profiles'].items() for key,row in rows.items() if not row['passed']]
    assert not missing, missing


if __name__ == '__main__': main()
