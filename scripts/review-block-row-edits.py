"""Read hosted scrollback-modes ZIPs, including failed baselines. Does not run a terminal."""
import argparse
from hashlib import sha256
from io import BytesIO
import json
from zipfile import ZipFile

from PIL import Image


# The terminal exposes half-open edges; these lists describe the actual printed
# cells on the screen, independently of the fixture's reported expectations.
KEEP = {'right-ich', 'right-dch', 'left-ich', 'left-dch', 'first-right', 'last-left',
        'other-row', 'bidi-right', 'scaled-right'}
LOST = {'through-text', 'cut-wide-edge', 'move-one-row', 'bidi-reorders', 'scaled-cut'}
KEY_CASES = {'right-ich', 'left-dch', 'bidi-right', 'scaled-right'}
ACTIONS = {'default': KEEP | LOST, 'copy-key': KEY_CASES,
           'copy-paste': KEY_CASES | {'cut-wide-edge', 'bidi-reorders'}}
ACK = b'\x1b[0n'
BUTTON = b'\x1b[<2;16;5M\x1b[<2;16;5m'


def review(path, bindings=False):
    def read(n):
        return json.loads(z.read(n).decode('utf-8-sig'))

    with ZipFile(path) as z:
        source = read('build/scrollback-modes-product/SOURCE-HOST.json')
        identity = source['Executable']['SHA256'].lower()
        rows = []
        for action in (ACTIONS if bindings else ['default']):
            suffix = '' if action=='default' else '-'+action
            for renderer in ('gdi', 'directx'):
                prefix = f'research/scrollback-block-edit-{renderer}{suffix}'
                if prefix+'.json' in z.namelist(): break
            else: raise ValueError('Missing '+action+' in '+str(path))
            trace = read(prefix+'-observed.json'); result = read(prefix+'.json')
            assert trace['executable_sha256'].lower() == identity
            assert trace['completed'] and not trace['cleanup']['terminated_remaining'] and not trace['cleanup']['remaining_processes']
            conf = trace['profile_values']; assert trace['requested_font']=='SarasaTermSC Nerd Light'
            assert conf['NemoRenderer']=={'gdi':0,'directx':2}[renderer] and bool(conf.get('RightClickCopyAndPaste',0))==(action=='copy-paste')
            assert set(result['cases'])==ACTIONS[action], (action,list(result['cases']),result.get('error'))
            cw,ch = result['cell']
            for label, rec in result['cases'].items():
                mid=list(range(7,10) if label.startswith('bidi-') else range(6,10) if label.startswith('scaled-') else range(6,11))
                full=[list(range(6,11)),mid,list(range(6,11))]; blank=[[],[],[]]
                text='中A文\r\n'+('בגד' if label.startswith('bidi-') else '中' if label.startswith('scaled-') else '中B文')+'\r\n中C文'
                keep=label in KEEP; issues=[]
                assert trace['cases'][label+'-seed']==(b'\x1b[?1002;1$y\x1b[?1006;1$y'+ACK).hex() and trace['cases'][label+'-edit']==ACK.hex()
                for stage,want in [('seed',blank),('drag',full),('edited',full if keep else blank)]:
                    im=Image.open(BytesIO(z.read(prefix+'-'+label+'-'+stage+'.png'))).convert('RGB')
                    assert im.size==(2+80*cw,2+24*ch)
                    marks=[[x for x in range(15) if im.getpixel((2+x*cw,2+y*ch))==(34,51,85)] for y in range(3)]
                    assert marks==rec[stage], (label,stage,'record differs from PNG')
                    if marks!=want: issues.append(stage+' pixels')
                assert rec['initial_copy']==text and rec['clipboard_after_edit']==text
                copied=rec.get('action_changed',rec.get('right_changed')); final=rec.get('action_text',rec.get('right_text'))
                if copied!=keep or final!=text: issues.append('clipboard')
                payload=(text.replace('\r\n','\r').encode() if action=='copy-paste' else b'') if keep else BUTTON
                if bytes.fromhex(rec['wire'])!=ACK+payload+b'8': issues.append('child input')
                assert rec['passed']==(not issues), (action,label,issues,rec)
                rows.append(dict(renderer=renderer,action=action,case=label,issues=issues))
        return dict(source=source['SourceCommit'],exe_sha256=identity,zip_sha256=sha256(path.read_bytes()).hexdigest(),cases=rows)


if __name__=='__main__':
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archives',type=Path,nargs='+');p.add_argument('--bindings',action='store_true');args=p.parse_args()
    reports=[review(path,args.bindings) for path in args.archives]
    print(json.dumps(reports,indent=2));raise SystemExit(int(any(case['issues'] for r in reports for case in r['cases'])))
