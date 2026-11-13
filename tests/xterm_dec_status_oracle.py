"""DEC status report wire behavior from the pinned XTerm on private Xvfb."""
import argparse
from xterm_state_oracle import run_cases


def cases():
    result = {}
    requests = ('', '0', '5', '6', '15', '25', '26', '53', '55', '56', '62',
                '63', '63;0', '63;1', '63;42', '63;65535', '63;65536',
                '63;999999999999999999999', '75', '85', '99', '999999999999999999999')
    for prefix in ('', '?'):
        for value in requests:
            result[prefix+(value or 'empty')] = '\x1b['+prefix+value+'n'
    for value in ('5;6', '6;5', '15;26', '26;0;1', '63;;9', '63;7;8',
                  '6:1', '6;0:1', '5:0', '63;7:0', '6;;', ';6'):
        result['arguments-'+value] = '\x1b[?'+value+'n'
    report = '\x1b[6n\x1b[?6n'
    result['position'] = '\x1b[9;17H'+report
    result['pending-wrap'] = '\x1b[24;80HX'+report+'Y'+report
    result['double-size'] = '\x1b#6'+'A'*40+report+'B'+report
    result['double-size-hidden'] = '\x1b#6\x1b[1;70H'+report
    result['unicode'] = '中e\u0301'+report
    result['vertical-origin'] = '\x1b[3;20r\x1b[?6h\x1b[5;7H'+report
    result['both-margins-origin'] = '\x1b[3;20r\x1b[?69h\x1b[11;70s\x1b[?6h\x1b[5;7H'+report
    result['both-margins-absolute'] = '\x1b[3;20r\x1b[?69h\x1b[11;70s\x1b[8;17H'+report
    result['origin-edges'] = '\x1b[3;20r\x1b[?69h\x1b[11;70s\x1b[?6h\x1b[999;999H'+report
    result['alternate'] = '\x1b[5;9H\x1b[?1049h\x1b[8;17H'+report+'\x1b[?1049l'+report
    result['soft-reset'] = '\x1b[3;20r\x1b[?6h\x1b[5;7H\x1b[!p'+report
    result['cancel'] = '\x1b[?6\x18n'+report
    result['recovery'] = '\x1b[?6\x1b[?5n'+report
    devices = ''.join('\x1b[?'+str(n)+'n' for n in (5,6,15,26,55,56,62,63,75,85))
    for level in range(61,66):
        result['level-'+str(level)] = f'\x1b[{level};1"p'+devices
        result['ris-level-'+str(level)] = f'\x1b[{level};1"p\x1bc'+devices
    return {name:'\x1b[65;1"p\x1bc'+sequence for name,sequence in result.items()}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output', default='research/dec-status-xterm.json')
    args=parser.parse_args()
    run_cases(args.xterm, args.output, cases(), ['-ti','vt525'])
