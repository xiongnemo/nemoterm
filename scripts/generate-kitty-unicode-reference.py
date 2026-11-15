"""Extract every Unicode-image state from the complete independent capture."""
import argparse
import base64
import copy
import hashlib
import json
import re
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


def emit(cases, array):
    lines=['static const KittyUnicodeReference '+array+'[] = {']
    for case in cases:
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
    return lines+['};','']


lines=['/* Generated from complete upstream Unicode-image capture SHA256 '+digest+'.',
    ' * All 97 cases / 728 states retained; normalized coordinates only convert',
    ' * to pixels using the captured geometry. No local placement model. */']
lines += emit(data['cases'],'kitty_unicode_reference')

# Eight explicit text-policy alternatives. Keep the original 728-state array
# intact. Every assertion still runs: only the expected cursor/text and the
# consequent placement translation/retention differ. No Nemoterm output is
# used to construct these alternatives.
xterm_sha='ea49c2d8830394edd8f156c3159a7cbfc66d9761d28a161640930d84ec1db3f2'
with tarfile.open(root/'research/kitty-unicode-evidence/xterm-text-cd69cc7.tar.gz') as tar:
    member=next(m for m in tar.getmembers() if m.name.endswith('/unicode-text-boundaries-xterm.json'))
    raw=tar.extractfile(member).read()
assert hashlib.sha256(raw).hexdigest()==xterm_sha
xterm=json.loads(raw)
assert xterm['version']=='XTerm(412)' and len(xterm['cases'])==26
def cursors(name):
    reply=bytes.fromhex(xterm['cases'][name]['reply_hex']).decode()
    return [(int(x)-1,int(y)-1) for y,x in re.findall(r'\x1b\[(\d+);(\d+)R',reply)]
def cells(name):
    reply=bytes.fromhex(xterm['cases'][name]['reply_hex']).decode()
    return [int(v,16) for v in re.findall(r'!~([0-9A-F]{4})',reply)]
for name in ('no-history','with-history'):
    assert cells('erase-'+name+'-3')==[65,66,32,32,32,32]*2
    assert cells('erase-'+name+'-2')==[65,66,32,32,32,32]+[32]*6
for mode,last in ((1047,4),(1049,2)):
    assert cursors('alternate-'+str(mode))==[(2,0),(2,0),(4,0),(last,0)]
    assert cells('alternate-'+str(mode))==[32,32,67,68,32,32,65,66,32,32,32,32]
for name,scalar in (('ascii',65),('placeholder',0xeeee)):
    for marks in ('','cc85','cc85cc85','cc85cc8d'):
        assert cursors('repeat-'+name+'-'+marks)==[(4,0)]
        assert cells('repeat-'+name+'-'+marks)==[scalar]*4+[32]*2

policies=[]
for case in data['cases']:
    if case['name'] in ('alternate-1047','alternate-1049'):
        captured=cursors(case['name'])
        steps=[]
        for original in case['steps']:
            label=original['label']
            if label not in ('enter','alternate-cells') and not (
                case['name']=='alternate-1047' and label in ('leave','erase-main')): continue
            state=copy.deepcopy(original)
            checkpoint=1 if label=='enter' else 2 if label=='alternate-cells' else 3
            state['cursor']=list(captured[checkpoint])
            if label=='alternate-cells':
                dx=captured[1][0]
                state['text'][0]=' '*dx+state['text'][0]
                for layer in state['layers']:
                    for edge in ('left','right'):
                        layer['dest_rect'][edge]+=2*dx/state['geometry']['columns']
            steps.append(state)
        policies.append(dict(name=case['name'],steps=steps))
    elif case['name']=='erase-history':
        before=next(s for s in case['steps'] if s['label']=='cells')
        steps=[]
        for original in case['steps']:
            if original['label'] not in ('operation','redraw'): continue
            state=copy.deepcopy(original)
            state['text'][0]=before['text'][0]
            state['layers']=copy.deepcopy(before['layers'])+state['layers']
            steps.append(state)
        policies.append(dict(name=case['name'],steps=steps))
assert sum(len(c['steps']) for c in policies)==8
lines += ['/* Explicit xterm text policy; independent wire capture SHA256',
          ' * '+xterm_sha+'.',
          ' * Original Kitty observations above are never overwritten. */']
lines += emit(policies,'kitty_unicode_xterm_policy')
text='\n'.join(lines)
path=root/'vendor/putty-0.85/test/kitty_unicode_reference.h'
parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
if args.check:
    assert path.read_text()==text, 'Unicode-image fixture differs from retained upstream'
else:
    path.write_text(text)
print('Kitty Unicode reference: all 97 cases / 728 raw states retained; 8 explicit xterm text-policy alternatives verified')
