"""Replay retained DECREQTPARM syntax through both Windows input code pages."""
import argparse
import json
import os
from pathlib import Path

from protocol_oracle_window import run

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--input-cp', type=int, choices=(28591, 65001))
args = parser.parse_args()
reference = json.loads(Path(__file__).with_name('legacy_parameter_reference.json').read_text())
assert len(reference['cases']) == 136

for code_page in ([args.input_cp] if args.input_cp else [28591, 65001]):
    os.environ['NEMOTERM_TEST_INPUT_CP'] = str(code_page)
    cases = []
    for case in reference['cases']:
        reply = bytes.fromhex(case['reply_hex'])
        if code_page == 65001:
            # ReadFile encodes the C1 input character using the console input CP.
            reply = b''.join(chr(b).encode('utf-8') if 0x80 <= b <= 0x9f
                             else bytes([b]) for b in reply)
        cases.append((case['name'], case['sequence'], reply))

    def check_input(hwnd, phase, current):
        observed = current()
        assert observed['input_cp'] == code_page, observed
        return dict(input_cp=code_page, physical_input=False, clipboard_access=False,
                    policy_differences=reference['policy_differences'])

    run('legacy-parameter-'+str(code_page), cases, exercise=check_input,
        barrier=('\x1b[5n', b'\x1b[0n'),
        profile=dict(NemoRenderer=0, NemoTabs=0, WarnOnClose=0),
        font='Consolas' if os.environ.get('CI') == 'true' else 'SarasaTermSC Nerd Font Light',
        source_reference='XTerm(412) VT100 syntax with explicit Nemoterm report policy')
