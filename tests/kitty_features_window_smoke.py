"""Replay independent feature-query wires through ConPTY, retaining seed pixels."""
import base64
import json
import os
from pathlib import Path
from sixel_palette_window_smoke import main, reset


def exercise(phase, block):
    reference = json.loads(Path(__file__).with_name('kitty_feature_reference.json').read_text())
    assert len(reference['cases']) == 84
    cell_width = (block(2, 'red')['x']-1)//2
    for case in reference['cases']:
        for index, step in enumerate(case['steps']):
            wire = base64.b64decode(step['input_base64']).decode('ascii')
            reply = base64.b64decode(step['reply_base64'])
            regions = [block(3, 'red', left=cell_width, count=2, height=2)]
            if case['name'].startswith('pending-') and step['label'] == 'last-chunk':
                regions.append(block(3, 'green', left=cell_width, count=1, height=1))
            phase(case['name']+'-'+step['label'], (reset() if index == 0 else '')+wire,
                  regions, expected_reply=reply)


if __name__ == '__main__':
    main(exercise, suite_name='kitty-features',
         font=os.environ.get('NEMOTERM_TEST_FONT', 'Consolas' if os.environ.get('CI') == 'true'
                             else 'SarasaTermSC Nerd Font Light'))
