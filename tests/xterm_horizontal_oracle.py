"""Capture horizontal edits on an independent XTerm in a private Xvfb display."""
import argparse
import json
import re
from pathlib import Path
from xterm_state_oracle import run_cases

CPR = '\x1b[6n'
CELLS = [(r, c) for r in range(1, 8) for c in range(1, 13)]
CELLS += [(r, c) for r in (1, 3, 6, 24) for c in (39, 40, 41, 79, 80)]
GRID = ''.join(f'\x1b[{r};1H' + ''.join(chr(65+(r+c)%26) for c in range(80))
               for r in range(1, 8))
OPS = {'back-index': '\x1b6', 'forward-index': '\x1b9',
       'left': '\x1b[2 @', 'right': '\x1b[2 A',
       'delete-columns': '\x1b[2\'~', 'insert-columns': '\x1b[2\'}',
       'down-alias': '\x1b[2^'}


def cases():
    result = {}
    for name, op in OPS.items():
        for region, setup in [('screen', ''), ('margins', '\x1b[?69h\x1b[3;8s\x1b[3;6r')]:
            for row, col in ((1, 1), (2, 3), (3, 3), (4, 5), (6, 8), (7, 8), (4, 1), (4, 10), (4, 80)):
                result[f'{name}-{region}-{row}-{col}'] = '\x1bc'+GRID+setup+f'\x1b[{row};{col}H'+op+CPR
        for count in ('', '0', '1', '6', '99', '2147483647', '2;9'):
            final = {'left': ' @', 'right': ' A', 'delete-columns': "'~", 'insert-columns': "'}", 'down-alias': '^'}.get(name)
            if final:
                result[f'{name}-count-{count or "default"}'] = '\x1bc'+GRID+'\x1b[?69h\x1b[3;8s\x1b[3;6r\x1b[4;5H\x1b['+count+final+CPR
        for variant, prefix in [('pending', '\x1b[3;80HX'), ('origin', '\x1b[?69h\x1b[3;8s\x1b[3;6r\x1b[?6h\x1b[2;1H'),
                                ('double', '\x1b[3;1H\x1b#6\x1b[3;40H'),
                                ('wide', '\x1b[3;1HA中BCD文EFG\x1b[?69h\x1b[3;8s\x1b[3;6r\x1b[3;3H'),
                                ('bce', '\x1b[?69h\x1b[3;8s\x1b[3;6r\x1b[4;3H\x1b[31;42m')]:
            result[f'{name}-{variant}'] = '\x1bc'+GRID+prefix+op+CPR+'Z'+CPR
    for name, op in [('up', '\x1b[S'), ('down', '\x1b[T')]:
        result[name+'-pending'] = '\x1bc'+GRID+'\x1b[3;80HX'+op+CPR+'Z'+CPR
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output', default='research/horizontal-xterm.json')
    args = parser.parse_args()
    originals = cases()
    suffix = '\x1b[?6l\x1b[?69l\x1b[31#y'+''.join(
        f'\x1b[{i};1;{r};{c};{r};{c}*y' for i, (r, c) in enumerate(CELLS, 1))
    run_cases(args.xterm, args.output, {n: s+suffix for n, s in originals.items()},
              ['-ti', 'vt520', '-xrm', '*allowWindowOps: true'])
    path = Path(args.output)
    data = json.loads(path.read_text(encoding='utf-8'))
    for name, case in data['cases'].items():
        checks = re.findall(r'\x1bP(\d+)!~([0-9A-Fa-f]+)\x1b\\', case['reply'])
        assert len(checks) == len(CELLS), (name, len(checks))
        case['input'] = originals[name]
        case['cursor_reply'] = case['reply'].split('\x1bP', 1)[0]
        case['cells'] = [dict(row=r, column=c, checksum=int(value, 16))
                         for (r, c), (_, value) in zip(CELLS, checks)]
    path.write_text(json.dumps(data, indent=2), encoding='utf-8')
