"""Extract literal image identity, deletion and scroll observations from kitty."""
import argparse,base64,gzip,hashlib,json,re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
raw=gzip.decompress((root/'research/kitty-reference-evidence/d638691-observations.json.gz').read_bytes())
digest='b00df940a8d246bfdc958ea46d67d8321d031d129b02db28cc2fe3b298a176a0'
assert hashlib.sha256(raw).hexdigest()==digest
data=json.loads(raw)
assert data['status']=='complete' and data['upstream_commit']=='8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f'
names=['replace-named-placement','anonymous-placement-ids','inside-scroll-region',
       'overlap-top-scroll-region','overlap-bottom-scroll-region']
lines=['/* Generated literal kitty states; capture SHA-256 '+digest+'.',
       ' * Cursor movement and APC parsing belong to separate integration tests. */',
       'static const Reference states[] = {']
for name in names:
    case=next(c for c in data['cases'] if c['name']==name)
    for index,state in enumerate(case['steps']):
        wire=base64.b64decode(state['input_base64'])
        header=wire.split(b'\x1b_G',1)[1].split(b';',1)[0].split(b'\x1b\\',1)[0].decode() if b'\x1b_G' in wire else ''
        values=dict(v.split('=') for v in header.split(',')) if header else {}
        if header:
            operation={'T':1,'p':2,'d':3}[values['a']]
        else:
            assert wire.endswith(b'\n') or wire.endswith(b'\x1bM')
            operation=4 if wire.endswith(b'\n') else 5
        if operation==1:width,height=int(values['s']),int(values['v'])
        assert len(state['layers'])<=2
        layers=[]
        for box,layer in zip(state['pixel_boxes'],state['layers']):
            vals=[box[k] for k in ('left','top','right','bottom')]+[layer['src_rect'][k] for k in ('left','top','right','bottom')]
            layers.append('{'+','.join(map(repr,vals))+'}')
        while len(layers)<2:layers.append('{0}')
        fields=[json.dumps(name+'/'+state['label']),json.dumps(header),str(int(index==0)),str(operation),
                str(width),str(height),*map(str,state['cursor']),str(state['image_count']),str(len(state['layers'])),
                '{'+','.join(layers)+'}']
        lines.append('    {'+','.join(fields)+'},')
lines.append('};\n');expected='\n'.join(lines).encode()
target=root/'tests/kitty_placement_reference.h'
parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
if args.check:
    assert target.read_bytes().replace(b'\r\n',b'\n')==expected
    print('Pinned kitty placements: 18 literal states verified')
else:target.write_bytes(expected)
