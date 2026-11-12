"""Independent DA/DA2/DA3/XTVERSION requests on a pinned XTerm and private Xvfb."""
import argparse
import json
from pathlib import Path

from xterm_state_oracle import run_cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--xterm', required=True)
    parser.add_argument('--output', default='research/identity-xterm.json')
    args = parser.parse_args()
    cases = {}
    for prefix, final in [('', 'c'), ('>', 'c'), ('=', 'c'), ('>', 'q')]:
        for arg in ('', '0', '00', '0;9', ';9', '1', '2', '1;0', '0:0',
                    '0:1', ':1', '0;1:2', '0:0:0', '1:0', '1;0:0'):
            cases[f'{prefix}{final}-{arg}'] = f'\x1b[{prefix}{arg}{final}'
    cases['visible'] = '\x1b[?25h\x1b[=c\x1b[?25$p'
    cases['hidden'] = '\x1b[?25l\x1b[=c\x1b[=1c\x1b[=2c\x1b[?25$p'
    run_cases(args.xterm, args.output, cases, ('-xrm', '*decTerminalID: 420'))
    data = json.loads(Path(args.output).read_text())
    replies = data['cases']
    # Different products have different DA identities. The argument rules,
    # framing and DA3 response are the independently comparable contract.
    for prefix, final in [('', 'c'), ('>', 'c'), ('=', 'c'), ('>', 'q')]:
        baseline = replies[f'{prefix}{final}-']['reply']
        assert baseline
        for arg in ('0', '00', '0;9', ';9', '0:0', '0:1', ':1', '0;1:2', '0:0:0'):
            assert replies[f'{prefix}{final}-{arg}']['reply'] == baseline, (prefix, final, arg)
        for arg in ('1', '2', '1;0', '1:0', '1;0:0'):
            assert replies[f'{prefix}{final}-{arg}']['reply'] == '', (prefix, final, arg)
    assert replies['=c-']['reply'] == '\x1bP!|00000000\x1b\\'
    assert replies['>q-']['reply'] == '\x1bP>|XTerm(412)\x1b\\'
    assert replies['visible']['reply'] == '\x1bP!|00000000\x1b\\\x1b[?25;1$y'
    assert replies['hidden']['reply'] == '\x1bP!|00000000\x1b\\\x1b[?25;2$y'
    print('Pinned XTerm identity request semantics verified')


if __name__ == '__main__':
    main()
