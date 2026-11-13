"""Collect independent XTerm replies; never substitute authored expectations.

Run in an authorized Linux test environment, including an isolated CI runner.
"""
import argparse
import json
from pathlib import Path
from selection_colour_cases import CASES, CSI, OSC, ST, QUERY, PREFIX
from xterm_state_oracle import run_cases

def cases():
    result = {name: sequence for name, sequence, _ in CASES}
    # Resource-dependent reset replies are captured, not guessed from Nemoterm.
    for command in (117, 119):
        for payload in ('', ';', ';ignored', ';?'):
            result[f'reset-{command}-{payload or "empty"}'] = \
                PREFIX+OSC+str(command)+payload+ST+QUERY
        result[f'reverse-reset-{command}'] = PREFIX+CSI+'?5h'+OSC+str(command)+ST+\
            QUERY+CSI+'?5l'+QUERY
    result['initial-resource-colours'] = CSI+'?5l'+OSC+'117'+ST+OSC+'119'+ST+QUERY
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output', default='research/selection-colour-xterm.json')
    args = parser.parse_args()
    run_cases(args.xterm, args.output, cases(), ['-ti', 'vt520',
        '-fg', '#ffffff', '-bg', '#000000',
        '-xrm', '*highlightColor: #ffffff', '-xrm', '*highlightTextColor: #000000'])
    captured = json.loads(Path(args.output).read_text(encoding='utf-8'))['cases']
    differences = [name for name, sequence, expected in CASES
                   if captured[name]['sequence'] != sequence or captured[name]['reply'] != expected]
    if differences:
        raise SystemExit('Authored expectations differ from retained XTerm evidence: '+
                         ', '.join(differences))
    print(f'{len(CASES)} authored expectations match the independent capture')
