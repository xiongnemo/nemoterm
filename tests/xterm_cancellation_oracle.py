"""Capture CAN/SUB effects from a fresh pinned XTerm for each input stream.

Inputs and literal controls are authored here. Expected cancellation behavior
is never computed: complete wire replies and Unicode cell checksums come from
the independent terminal. All windows use private remote Xvfb displays.
"""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import re
from xterm_state_oracle import run_cases

E = b'\x1b'
C = E + b'['
ST = E + b'\\'
REPORT = C + b'1$w'
RESET = C + b'?42l' + E + b'%G' + E + b'c' + E + b'%@' + E + b'c' + C + b'65;1"p'
CELLS = [(1, i) for i in range(1, 9)]
PREFIXES = {
    'ground': b'', 'escape': E, 'escape-intermediate': E + b' ',
    'charset': E + b'(', 'charset-intermediate': E + b'(%', 'docs': E + b'%',
    'csi-parameters': C + b'1;2', 'csi-intermediate': C + b'1$',
    'csi-ignore': C + b'1$:', 'osc-start': E + b']', 'osc-number': E + b']2',
    'osc-string': E + b']2;unfinished', 'osc-escape': E + b']2;unfinished' + E,
    'dcs-header': E + b'P1;', 'dcs-status-query': E + b'P$qm',
    'dcs-cursor-restore': E + b'P1$t1;1;1;@',
    'dcs-upss': E + b'P0!u%', 'dcs-escape': E + b'P$qm' + E,
    'sixel-header': E + b'P0;1', 'sixel-data': E + b'P0;1q#1;2;100;0;0~',
    'apc': E + b'_unfinished', 'pm': E + b'^unfinished', 'sos': E + b'Xunfinished',
}


def cases():
    result = {}

    def add(name, encoding, body, setup=b'', cells=CELLS, **metadata):
        assert name not in result
        coding = E + (b'%G' if encoding == 'utf8' else b'%@')
        suffix = E + b' F' + C + b'65;1"p' + C + b'31#y'
        suffix += b''.join(C + f'{i};1;{row};{col};{row};{col}*y'.encode()
                           for i, (row, col) in enumerate(cells, 1))
        # ST makes observation possible even if a cancellation is ignored.
        # The printable marker precedes ST, so a still-open string swallows
        # it and yields a different independent screen/cursor observation.
        stream = RESET + coding + C + b'2J' + C + b'H' + setup + REPORT + body + ST + REPORT + C + b'6n' + suffix
        result[name] = dict(sequence=stream, encoding=encoding, cells=cells, **metadata)

    for encoding in ('bytes', 'utf8'):
        add(f'{encoding}-literal-ascii', encoding, b'A', cells=[(1, 1)], control=[0x41])
        literal = b'&' if encoding == 'bytes' else '\u2426'.encode()
        add(f'{encoding}-literal-error-shape', encoding, literal, cells=[(1, 1)],
            control=[0x26 if encoding == 'bytes' else 0x2426])
        for cancel, value in (('can', b'\x18'), ('sub', b'\x1a')):
            for state, prefix in PREFIXES.items():
                add(f'{encoding}-{cancel}-{state}', encoding, b'A' + prefix + value + b'[B',
                    cancel=cancel, state=state)
            for level in range(1, 5):
                for state in ('ground', 'escape-intermediate', 'csi-parameters', 'osc-string', 'dcs-status-query'):
                    add(f'{encoding}-{cancel}-dec{level}-{state}', encoding,
                        b'A' + PREFIXES[state] + value + b'[B',
                        setup=C + f'{60+level};1"p'.encode(), cancel=cancel, dec_level=level, state=state)
            banks = {
                'g0-ascii': E + b'(B', 'g0-dec-line': E + b'(0',
                'g0-finnish': C + b'?42h' + E + b'(5',
                'g1-dec-line': E + b')0' + b'\x0e',
                'g2-finnish': C + b'?42h' + E + b'*5' + E + b'n',
                'g3-french': C + b'?42h' + E + b'+R' + E + b'o',
                'ss2': C + b'?42h' + E + b'*5' + E + b'N',
                'ss3': C + b'?42h' + E + b'+R' + E + b'O',
            }
            for bank, select in banks.items():
                add(f'{encoding}-{cancel}-{bank}', encoding,
                    b'A' + select + E + b' ' + value + b'[B', cancel=cancel, bank=bank)
            for boundary, setup, cells in (
                ('pending-wrap', C + b'1;80H', [(1, 80), (2, 1), (2, 2), (2, 3), (2, 4)]),
                ('no-wrap', C + b'?7l' + C + b'1;80H', [(1, 79), (1, 80), (2, 1)]),
                ('scroll-bottom', C + b'24;80H', [(23, 80), (24, 1), (24, 2), (24, 3), (24, 4)]),
                ('insert', b'WXYZ' + C + b'H' + C + b'4h', [(1, i) for i in range(1, 9)]),
            ):
                add(f'{encoding}-{cancel}-{boundary}', encoding,
                    b'A' + E + b' ' + value + b'[B', setup=setup, cells=cells,
                    cancel=cancel, boundary=boundary)
            for state, prefix in (('ground', b''), ('escape', E), ('intermediate', E + b' ')):
                # Exit VT52 before sending observation queries. The marker
                # avoids '[' here, since it can be mistaken for CSI after ESC.
                add(f'{encoding}-{cancel}-vt52-{state}', encoding,
                    C + b'?2l' + b'A' + prefix + value + b'BC' + E + b'<',
                    cancel=cancel, state=state, vt52=True)
    for cancel, value in (('can', b'\x18'), ('sub', b'\x1a')):
        for prefix in (b'\xe2', b'\xe2\x82', b'\xf0\x9f'):
            add(f'utf8-{cancel}-partial-{prefix.hex()}', 'utf8', b'A' + prefix + value + b'[B',
                cancel=cancel, state='partial UTF-8')
        for name, prefix in (('csi', b'\x9b1;2'), ('dcs', b'\x90$qm'),
                             ('osc', b'\x9d2;unfinished'), ('apc', b'\x9funfinished'),
                             ('pm', b'\x9eunfinished'), ('sos', b'\x98unfinished')):
            add(f'bytes-{cancel}-c1-{name}', 'bytes', b'A' + prefix + value + b'[B',
                cancel=cancel, state='C1 ' + name)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    parts = args.output.with_suffix(''); parts.mkdir(exist_ok=False)
    options = ['-ti', 'vt525', '-xrm', '*allowWindowOps: true',
               '-xrm', '*locale: false', '-xrm', '*wideChars: true']
    result = {}; authored = cases()
    for index, (name, case) in enumerate(authored.items()):
        path = parts / f'{index:03}.json'
        with path.with_suffix('.log').open('w') as log, redirect_stdout(log):
            run_cases(args.xterm, path, {name: case['sequence']}, options,
                      raw_replies=True, utf8_command_line=False)
        captured = json.loads(path.read_text())
        if not result:
            result = {**captured, 'cases': {}, 'scope': 'Independent stored Unicode cells and wire replies; no product expectations.'}
        assert result['executable_sha256'] == captured['executable_sha256']
        observation = captured['cases'][name]
        checksums = re.findall(rb'\x1bP([0-9]+)!~([0-9A-Fa-f]{4})\x1b\\', bytes.fromhex(observation['reply_hex']))
        assert [int(n) for n, _ in checksums] == list(range(1, len(case['cells']) + 1)), (name, checksums)
        observation.update({key: value for key, value in case.items() if key != 'sequence'})
        observation['unicode_cells'] = [int(value, 16) for _, value in checksums]
        result['cases'][name] = observation
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        if 'control' in case:
            assert observation['unicode_cells'] == case['control'], (name, observation)
        if (index + 1) % 25 == 0 or index + 1 == len(authored):
            print(index + 1, 'independent cancellation streams retained', flush=True)
    result['completed'] = True
    args.output.write_text(json.dumps(result, indent=2) + '\n')
