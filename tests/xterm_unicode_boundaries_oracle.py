"""Observe text semantics implicated by Unicode-image comparison failures.

XTerm does not implement Kitty graphics. These streams deliberately contain
only text controls, independent of either implementation's placement model.
"""
import argparse
from xterm_state_oracle import run_cases

C = '\x1b['
CPR = C + '6n'
CELLS = C + '31#y' + ''.join(
    C + f'{n};1;1;{n};1;{n}*y' for n in range(1, 7))


def cases():
    result = {}
    for name, char in [('ascii', 'A'), ('placeholder', '\U0010eeee')]:
        for marks in ['', '\u0305', '\u0305\u0305', '\u0305\u030d']:
            result[f'repeat-{name}-{marks.encode().hex()}'] = (
                '\x1bc' + char + marks + CPR + C + '3b' + CPR + CELLS)
    for mode in [47, 1047, 1049]:
        result[f'alternate-{mode}'] = (
            '\x1bcAB' + CPR + C + f'?{mode}h' + CPR + 'CD' + CPR + CELLS
            + C + f'?{mode}l' + CPR + CELLS)
        result[f'alternate-reenter-{mode}'] = (
            '\x1bcAB' + C + f'?{mode}h' + C + '3;5H' + 'Z'
            + C + f'?{mode}l' + CPR + C + f'?{mode}h' + CPR + CELLS
            + C + f'?{mode}l' + CPR)
    for kind, prefix in [('no-history', ''), ('with-history', 'history\r\n' * 30)]:
        for mode in [2, 3]:
            result[f'erase-{kind}-{mode}'] = (
                '\x1bc' + prefix + C + '2J' + C + 'HAB' + CPR + CELLS
                + C + f'{mode}J' + CPR + CELLS)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run_cases(args.xterm, args.output, cases(),
              ['-ti', 'vt520', '-xrm', '*allowWindowOps: true'], raw_replies=True)
    print('Retained 18 independent text-boundary streams including controls')
