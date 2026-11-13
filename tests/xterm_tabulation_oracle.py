"""Tabulation reference replies from XTerm on an owned, headless Xvfb display."""
import argparse
from xterm_state_oracle import run_cases


def cases():
    cpr = '\x1b[6n'
    result = {}
    for op, command in [('ht', '\t'), ('cht', '\x1b[I'), ('cbt', '\x1b[Z')]:
        for column in [1, 8, 9, 10, 40, 72, 73, 79, 80]:
            result[f'{op}-column-{column}'] = f'\x1b[1;{column}H' + command + cpr
        result[f'{op}-no-stops'] = '\x1b[3g\x1b[1;40H' + command + cpr
        result[f'{op}-custom-stops'] = ('\x1b[3g\x1b[1;5H\x1bH\x1b[1;18H\x1bH'
                                       '\x1b[1;10H' + command + cpr + command + cpr)
        for line in ['#3', '#4', '#6']:
            result[f'{op}-double-{line}'] = '\x1b' + line + '\x1b[1;39H' + command + cpr
        result[f'{op}-pending-wrap'] = '\x1b[1;80HX' + command + cpr + 'Y' + cpr
        result[f'{op}-double-wrap'] = '\x1b#6\x1b[1;40HX' + command + cpr + 'Y' + cpr
        for column in [1, 5, 9, 17, 20, 24, 25, 40, 80]:
            result[f'{op}-margins-{column}'] = ('\x1b[?69h\x1b[5;20s' +
                f'\x1b[1;{column}H' + command + cpr)
        result[f'{op}-origin'] = '\x1b[?69h\x1b[5;20s\x1b[3;8r\x1b[?6h' + command + cpr
    for final in ['I', 'Z']:
        for arg in ['', '0', '1', '2', '100', '4294967295', '999999999999999999999', '2;3', '1:2']:
            result[f'{final}-argument-{arg}'] = '\x1b[1;40H\x1b[' + arg + final + cpr
        result[f'{final}-cancelled'] = '\x1b[1;40H\x1b[2\x18' + final + cpr
    result['clear-current'] = '\x1b[1;9H\x1b[g\x1b[1;1H\t' + cpr
    result['clear-multiple'] = '\x1b[1;9H\x1b[0;3g\x1b[1;1H\t' + cpr
    for arg in ['', '0', '3', '5', '5;0', '0;5', '5:1']:
        result[f'restore-{arg}'] = '\x1b[3g\x1b[1;5H\x1bH\x1b[?' + arg + 'W\x1b[1;1H\t' + cpr + '\t' + cpr
    result['restore-pending-wrap'] = '\x1b[1;80HX\x1b[?5WY' + cpr
    result['soft-reset-stops'] = '\x1b[3g\x1b[1;5H\x1bH\x1b[!p\x1b[1;1H\x1b[I' + cpr
    result['hard-reset-stops'] = '\x1b[3g\x1b[1;5H\x1bH\x1bc\x1b[I' + cpr
    result['alternate-shared-stops'] = ('\x1b[3g\x1b[1;5H\x1bH\x1b[?1049h\x1b[I' + cpr +
        '\x1b[1;18H\x1bH\x1b[?1049l\x1b[I' + cpr)
    return {name: '\x1bc' + sequence for name, sequence in result.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output', default='research/tabulation-xterm.json')
    args = parser.parse_args()
    run_cases(args.xterm, args.output, cases(), ['-ti', 'vt520'])
