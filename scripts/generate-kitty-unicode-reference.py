"""Extract every Unicode-image state from the complete independent capture."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import tarfile

root=Path(__file__).resolve().parents[1]
archive=root/'research/kitty-unicode-evidence/upstream-reference.tar.gz'
digest='feda36b2971fbc29059b4c80ddf989c228e8c4b5c18ffe07fb064b05bbd78a44'
with tarfile.open(archive,'r:gz') as tar:
    raw=tar.extractfile('reference/observations.json').read()
assert hashlib.sha256(raw).hexdigest()==digest
data=json.loads(raw)
assert data['status']=='complete' and data['upstream_commit']=='8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f'
assert (data['case_count'],data['state_count'],len(data['diacritic_codepoints']))==(97,728,297)
assert data['upstream_tests']['successful'] and not data['upstream_tests']['skipped']


def literal(raw):
    def quote(part):
        return '"'+''.join('\\%03o'%c if c<32 or c>=127 else
            '\\'+chr(c) if c in (34,92) else chr(c) for c in part)+'"'
    return '\n        '.join(quote(raw[i:i+512]) for i in range(0,len(raw),512)) or '""'


lines=['/* Generated from complete upstream Unicode-image capture SHA256 '+digest+'.',
    ' * All 97 cases / 728 states retained; normalized coordinates only convert',
    ' * to pixels using the captured geometry. No local placement model. */',
    'static const KittyUnicodeReference kitty_unicode_reference[] = {']
for case in data['cases']:
    for index,state in enumerate(case['steps']):
        wire=base64.b64decode(state['input_base64']);reply=base64.b64decode(state['reply_base64'])
        operation=state['operation'];assert set(operation)<= {'resize','scroll'}
        rows,columns=operation.get('resize',[0,0])
        amount,up=operation.get('scroll',[0,False])
        scroll=-amount if up else amount
        error_prefix=0
        if b':' in reply:
            assert reply.startswith(b'\x1b_G') and reply.count(b'\x1b\\')==1 and reply.endswith(b'\x1b\\')
            error_prefix=reply.index(b':')+1
        g=state['geometry'];assert g['cell_width']==10 and g['cell_height']==20
        assert 0<g['columns']<=64 and 0<g['rows']<=16
        assert len(state['text'])==g['rows'] and all(not s.endswith(' ') for s in state['text'])
        assert len(state['layers'])<=16
        boxes=[]
        for layer in state['layers']:
            dest=layer['dest_rect'];src=layer['src_rect']
            values=[(dest['left']+1)*g['columns']*5,(1-dest['top'])*g['rows']*10,
                    (dest['right']+1)*g['columns']*5,(1-dest['bottom'])*g['rows']*10]
            values += [src['left'],src['top'],src['right'],src['bottom'],layer['z_index']]
            boxes.append('{'+','.join(format(v,'.17g') for v in values)+'}')
        x,y=state['cursor']
        fields=[int(index==0),g['columns'],g['rows'],columns,rows,scroll,x,y,
                state['image_count'],state['scrolled_by'],len(boxes),error_prefix]
        lines += ['    {'+literal((case['name']+'/'+state['label']).encode())+','+','.join(map(str,fields))+',',
                  '        '+literal(wire)+',','        '+literal(reply)+',',
                  '        {'+','.join(literal(s.encode()) for s in state['text'])+'},',
                  '        {'+(','.join(boxes) if boxes else '{0}')+'}},']
lines += ['};','']
text='\n'.join(lines)
path=root/'vendor/putty-0.85/test/kitty_unicode_reference.h'
parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
if args.check:
    assert path.read_text()==text, 'Unicode-image fixture differs from retained upstream'
else:
    path.write_text(text)
print('Kitty Unicode reference: all 97 cases / 728 states and text verified')
