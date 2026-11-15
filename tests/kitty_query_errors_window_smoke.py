"""Replay pending-upload header orders/errors through native ConPTY and pixels."""
import base64,json,os
from pathlib import Path
from sixel_palette_window_smoke import main,reset

def exercise(phase,block):
    reference=json.loads(Path(__file__).with_name('kitty_query_error_reference.json').read_text())
    assert len(reference['cases'])==54
    cell_width=(block(2,'red')['x']-1)//2
    for case in reference['cases']:
        for index,step in enumerate(case['steps']):
            wire=base64.b64decode(step['input_base64']).decode('ascii')
            reply=base64.b64decode(step['reply_base64'])
            regions=[block(3,'red',left=cell_width,count=2,height=2)]
            if step['complete_images']==2:
                regions.append(block(3,'green',left=cell_width,count=1,height=1))
            expectation={'expected_error_reply' if step['error_envelope_only'] else 'expected_reply':reply}
            phase(case['name']+'-'+step['label'],(reset() if index==0 else '')+wire,regions,**expectation)

if __name__=='__main__':
    main(exercise,suite_name='kitty-query-errors',
         font=os.environ.get('NEMOTERM_TEST_FONT','Consolas' if os.environ.get('CI')=='true'
                             else 'SarasaTermSC Nerd Font Light'))
