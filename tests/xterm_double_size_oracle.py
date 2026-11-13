"""Double-size row cursor and cell evidence from an owned XTerm/Xvfb instance."""
import argparse
import json
import re
from pathlib import Path
from xterm_state_oracle import run_cases

CPR = '\x1b[6n'
CELLS = [(r, c) for r in (1, 2, 3) for c in (1, 2, 3, 38, 39, 40, 41, 79, 80)]


def cases():
    result = {}
    for mode in (3, 4, 6):
        line = f'\x1b#{mode}'
        tests = {
            'ascii-edge': 'A'*40 + CPR + 'B' + CPR,
            'ascii-next-normal': 'A'*40 + 'B'*80 + CPR + 'C' + CPR,
            'wide-edge': '中'*20 + CPR + '文' + CPR,
            'wide-cross-edge': 'A'*39 + '中' + CPR + 'Z' + CPR,
            'combining-edge': 'A'*39 + 'e\u0301' + CPR + 'Z' + CPR,
            'nowrap': '\x1b[?7l' + 'A'*40 + 'BC' + CPR,
            'position': '\x1b[1;79H' + CPR + 'X' + CPR,
            'relative-right': '\x1b[99C' + CPR + 'X' + CPR,
            'save-restore-wrap': 'A'*40 + '\x1b7\x1b[3;1H\x1b8' + CPR + 'Z' + CPR,
            'next-double': '\x1b[2;1H' + line + '\x1b[1;1H' + 'A'*80 + CPR + 'Z' + CPR,
            'next-double-wide': '\x1b[2;1H' + line + '\x1b[1;1H' + 'A'*39 + '中'*20 + CPR,
            'lf-to-double': '\x1b[2;1H' + line + '\x1b[1;39H\n' + CPR + 'ABC' + CPR,
            'ri-to-double': '\x1b[2;1H\x1b[60G\x1bM' + CPR + 'X' + CPR,
            'normal-to-double': '\x1b#5\x1b[1;60H' + line + CPR + 'X' + CPR,
            'shrink-existing': '\x1b#5' + 'A'*39 + '中文' + line + CPR + '\x1b#5' + CPR,
            'grow-pending': 'A'*40 + '\x1b#5' + CPR + 'Z' + CPR,
        }
        for name, sequence in tests.items():
            result[f'{mode}-{name}'] = '\x1bc' + line + sequence
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output', default='research/double-size-xterm.json')
    args = parser.parse_args()
    originals = cases()
    suffix = '\x1b[23#y' + ''.join(f'\x1b[{i};1;{r};{c};{r};{c}*y'
        for i, (r, c) in enumerate(CELLS, 1))
    run_cases(args.xterm, args.output, {n: s+suffix for n, s in originals.items()},
        ['-ti', 'vt520', '-xrm', '*allowWindowOps: true'])
    path = Path(args.output)
    data = json.loads(path.read_text())
    for name, case in data['cases'].items():
        checks = re.findall(r'\x1bP(\d+)!~([0-9A-Fa-f]+)\x1b\\', case['reply'])
        assert len(checks) == len(CELLS), (name, checks)
        case['input'] = originals[name]
        case['cursor_reply'] = case['reply'].split('\x1bP', 1)[0]
        case['cells'] = [dict(row=r, column=c, checksum=int(value, 16))
            for (r, c), (_, value) in zip(CELLS, checks)]
    path.write_text(json.dumps(data, indent=2))
