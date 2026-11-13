"""XTSMGRAPHICS protocol replies from an independent, headless XTerm."""
import argparse
from xterm_state_oracle import run_cases


def cases():
    query = lambda parameters: '\x1b[?'+parameters+'S'
    result = {}
    for parameters in ['1;1;0', '1;4;0', '1;0;0', '1;5;0', '1;99;0',
        '1;3;0', '1;3;1', '1;3;2', '1;3;16', '1;3;255', '1;3;256',
        '1;3;257', '1;3;1024', '1;3;1025', '1;3;999999999999999999999',
        '2;1;0', '2;4;0', '2;2;0', '2;3;0', '2;0;0', '2;5;0',
        '3;1;0', '3;2;0', '3;4;0', '4;1;0', '0;1;0', '99;1;0',
        '1;1', '1', '', '1;1;0;0', '2;3;80;24', '1;3;2:3',
        ';1;0', '1;;0', '1;1;', '1;2;0']:
        result[parameters or 'empty'] = query(parameters)+query('1;1;0')
    result['soft-reset'] = query('1;3;16')+'\x1b[!p'+query('1;1;0')
    result['hard-reset'] = query('1;3;16')+'\x1bc'+query('1;1;0')
    result['alternate'] = query('1;3;16')+'\x1b[?1049h'+query('1;1;0')+'\x1b[?1049l'+query('1;1;0')
    result['cancel'] = '\x1b[?1;3;2\x18S'+query('1;1;0')
    return {name: query('1;3;256')+sequence for name, sequence in result.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output', default='research/graphics-query-xterm.json')
    args = parser.parse_args()
    run_cases(args.xterm, args.output, cases(), ['-ti', 'vt340', '-xrm', '*allowWindowOps: true'])
