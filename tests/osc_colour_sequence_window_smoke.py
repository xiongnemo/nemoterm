"""Replay unchanged XTerm colour-command replies through owned native ConPTY."""
import json
import os
from pathlib import Path
from protocol_oracle_window import run

reference = json.loads(Path(__file__).with_name('osc_colour_sequence_reference.json').read_text())
assert len(reference['cases']) == 64 and len(reference['observed_syntax_differences']) == 8
os.environ['NEMOTERM_TEST_INPUT_CP'] = '65001'
cases = [(case['name'], case['sequence'], bytes.fromhex(case['reply_hex'])) for case in reference['cases']]

def verify(hwnd, phase, current):
    observed = current()
    assert observed['input_cp'] == 65001
    return dict(input_cp=65001, physical_input=False, clipboard_access=False,
                syntax_differences=reference['policy_differences'])

run('osc-colour-sequence', cases, exercise=verify,
    barrier=('\x1b[5n', b'\x1b[0n'),
    profile=dict(NemoRenderer=0, NemoTabs=0, WarnOnClose=0),
    font='Consolas' if os.environ.get('CI') == 'true' else 'SarasaTermSC Nerd Font Light',
    source_reference='XTerm(412): 64 unchanged colour-sequence replies; eight Xlib syntax differences retained separately')
