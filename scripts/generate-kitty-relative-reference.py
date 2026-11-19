"""Extract all relative-placement replay states from the retained upstream capture."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import tarfile

root=Path(__file__).resolve().parents[1]
archive=root/'testdata/upstream/kitty-relative-evidence/upstream-reference.tar.gz'
digest='0382ddf7f09f8c6c7d47f4a751447dabb31ac472c1714a4ce6b4d1bfd4e83d98'
with tarfile.open(archive,'r:gz') as tar:
    raw=tar.extractfile('reference/observations.json').read()
assert hashlib.sha256(raw).hexdigest()==digest
d=json.loads(raw)
assert d['status']=='complete' and d['upstream_commit']=='8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f'
assert d['upstream_tests']['successful'] and not d['upstream_tests']['skipped']
assert d['geometry']==dict(columns=12,rows=8,cell_width=10,cell_height=20)
assert (d['case_count'],d['state_count'])==(60,238)

def literal(raw):
    def quote(part):
        return '"' + ''.join('\\%03o'%c if c<32 or c>=127 else
            '\\'+chr(c) if c in (34,92) else chr(c) for c in part) + '"'
    return '\n        '.join(quote(raw[i:i+512]) for i in range(0,len(raw),512)) or '""'

lines=['/* Generated from upstream capture SHA256 '+digest+'.',
    ' * No reply, input, layer or lifecycle state is omitted.',
    ' * Coordinates only convert normalized upstream values to the captured 120x160 pixels.',
    ' * Error messages retain raw bytes; replay checks exact ID/status and a nonempty detail. */',
    'static const KittyRelativeReference kitty_relative_reference[] = {']
for case in d['cases']:
    for index,state in enumerate(case['steps']):
        wire=base64.b64decode(state['input_base64'])
        reply=base64.b64decode(state['reply_base64'])
        error_prefix=0
        if b':' in reply:
            assert reply.startswith(b'\x1b_G') and reply.count(b'\x1b\\')==1 and reply.endswith(b'\x1b\\')
            error_prefix=reply.index(b':')+1
        boxes=[]
        assert len(state['layers'])<=12
        for layer in state['layers']:
            dst=layer['dest_rect'];src=layer['src_rect']
            values=[(dst['left']+1)*60,(1-dst['top'])*80,
                    (dst['right']+1)*60,(1-dst['bottom'])*80]
            values.extend(src[k] for k in ('left','top','right','bottom'))
            values.append(layer['z_index'])
            boxes.append('{'+','.join(repr(v) for v in values)+'}')
        fields=[json.dumps(case['name']+'/'+state['label']),str(int(index==0)),
            *map(str,state['cursor']),str(state['image_count']),str(state['scrolled_by']),
            str(len(state['layers'])),str(error_prefix),literal(wire),literal(reply),
            '{'+','.join(boxes or ['{0}'])+'}']
        lines.append('    {'+','.join(fields)+'},')
lines.append('};\n')
expected='\n'.join(lines).encode()
target=root/'vendor/putty-0.85/test/kitty_relative_reference.h'
parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
if parser.parse_args().check:
    assert target.read_bytes().replace(b'\r\n',b'\n')==expected,'Regenerate Kitty relative reference'
    print('Kitty relative reference: all 60 cases / 238 states verified')
else:
    target.write_bytes(expected)
