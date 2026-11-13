"""Independent reference collector, prepared but not executed.

Run after runtime testing resumes. Explicit special-colour resources make the
reset expectations independent of the user's XTerm resource database.
"""
import argparse
import json
from pathlib import Path
from attribute_colour_cases import CASES
from xterm_state_oracle import run_cases

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output', default='research/attribute-colour-xterm.json')
    args = parser.parse_args()
    resources = ['-ti', 'vt520', '-fg', '#ffffff', '-bg', '#000000']
    for mode in ('BD', 'UL', 'BL', 'RV', 'IT'):
        resources += ['-xrm', f'*color{mode}: #ffffff']
    run_cases(args.xterm, args.output, {name: sequence for name, sequence, _ in CASES},
              resources, raw_replies=True)
    actual = json.loads(Path(args.output).read_text(encoding='utf-8'))['cases']
    differences = [name for name, sequence, expected in CASES
                   if actual[name]['sequence'] != sequence or
                   actual[name]['reply_hex'] != expected.encode().hex()]
    if differences:
        raise SystemExit('Reference differences retained: '+', '.join(differences))
    print(f'{len(CASES)} authored expectations match independent wire replies')
