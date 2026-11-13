"""Independent cursor/charset collector for an authorized Linux test environment."""
import argparse
import json
from pathlib import Path
from cursor_charset_cases import CASES
from xterm_state_oracle import run_cases

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output', default='research/cursor-charset-xterm.json')
    args = parser.parse_args()
    run_cases(args.xterm, args.output, {name: sequence for name, sequence, _ in CASES},
              ['-ti', 'vt520', '-xrm', '*allowWindowOps: true'], raw_replies=True)
    actual = json.loads(Path(args.output).read_text(encoding='utf-8'))['cases']
    differences = [name for name, sequence, expected in CASES
                   if actual[name]['sequence'] != sequence or
                   actual[name]['reply_hex'] != expected.encode().hex()]
    if differences:
        raise SystemExit('Reference differences retained: '+', '.join(differences))
    print(f'{len(CASES)} authored expectations match independent wire replies')
