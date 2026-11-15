"""Configured PuTTY-style answerback escapes through native ConPTY."""
import argparse
import os
from protocol_oracle_window import run

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--input-cp', type=int, choices=(28591, 65001))
args = parser.parse_args()
ESC, CSI = '\x1b', '\x1b['
RESET = CSI+'65;1"p'+ESC+'c'+ESC+' F'
FINISH = ESC+'<'+CSI+'65;1"p'+ESC+' F'
operations = [('initial', ''), ('soft-reset', CSI+'!p'), ('hard-reset', ESC+'c'),
              ('alternate', CSI+'?1049h'), ('saved-cursor', ESC+'7'+CSI+'2;3H'+ESC+'8'),
              ('utf8-on', ESC+'%G'), ('utf8-off', ESC+'%@'),
              ('level-61', CSI+'61;1"p'), ('vt52', CSI+'?2l')]
profiles = [
    ('literal', 'LEFT^!^0^ ^:^/RIGHT^~END', b'LEFT^!^0^ ^:^/RIGHT^END'),
    ('controls', '^M^J^@^<0x1b>^?^~', b'\r\n\0\x1b\x7f^'),
    ('numeric', '^<13>^<015>^<0x0d>^<0>', b'\r\r\r\0'),
    ('empty', '', b''),
]
for code_page in ([args.input_cp] if args.input_cp else [28591, 65001]):
    os.environ['NEMOTERM_TEST_INPUT_CP'] = str(code_page)
    for label, configured, reply in profiles:
        cases = [(framing+'-'+name, RESET+ESC+' '+framing+operation+'\x05'+FINISH, reply)
                 for framing in ('F', 'G') for name, operation in operations]
        cases += [('within-csi', RESET+CSI+'6\x05n'+FINISH, reply+b'\x1b[1;1R'),
                  ('within-osc', RESET+ESC+']0;NEMO\x05REF'+ESC+'\\'+FINISH, b'')]

        def verify(hwnd, phase, current):
            observed = current()
            assert observed['input_cp'] == code_page, observed
            return dict(input_cp=code_page, physical_input=False, clipboard_access=False)

        run('answerback-config-'+label+'-'+str(code_page), (), extra_cases=cases, exercise=verify,
            barrier=(CSI+'5n', b'\x1b[0n'),
            profile=dict(NemoRenderer=0, NemoTabs=0, WarnOnClose=0, Answerback=configured),
            font='Consolas' if os.environ.get('CI') == 'true' else 'SarasaTermSC Nerd Font Light',
            source_reference='PuTTY-style configuration contract; not an XTerm reply projection')
