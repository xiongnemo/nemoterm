"""Project complete OSC payload cases from the retained independent capture.

The full 117-case/555-stage capture is retained unchanged. The component gets
complete OSC payload cases; a second projection replays every input byte and
original chunk boundary through the real terminal parser.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import tarfile

root=Path(__file__).resolve().parents[1]
digest='4060b1bc1cde1302da9874c804e4d83d66d95a0bfb47b5a1dbf8401a2081d81e'
with tarfile.open(root/'testdata/upstream/pointer-shape-evidence/kitty-reference-ed5beca.tar.gz') as tar:
    raw=tar.extractfile('reference/observations.json').read()
assert hashlib.sha256(raw).hexdigest()==digest
data=json.loads(raw)
assert data['status']=='complete' and (data['case_count'],data['state_count'])==(117,555)

def literal(raw):
    return '"'+''.join('\\%03o'%c if c<32 or c>=127 else
        '\\'+chr(c) if c in (34,92) else chr(c) for c in raw)+'"'

excluded=[];selected=[]
for case in data['cases']:
    if case['name'].startswith(('screen-','reset-','mouse-','erase-','cancel-','embedded-')):
        excluded.append(case['name'])
    else:
        selected.append(case)
assert len(selected)==106 and len(excluded)==11
lines=['/* Generated from independent upstream capture '+digest+'.',
       ' * Complete OSC payload component projection; full VT cases remain in the source archive. */',
       'static const PointerReference pointer_reference[] = {']
for case in selected:
    for i,stage in enumerate(case['steps']):
        wire=base64.b64decode(stage['input_base64'],validate=True)
        reply=base64.b64decode(stage['reply_base64'],validate=True)
        fields=[json.dumps(case['name']+'/'+stage['label']),str(int(i==0)),literal(wire),str(len(wire)),
                literal(reply),str(len(reply)),json.dumps(stage['current_shape'])]
        lines.append('    {'+', '.join(fields)+'},')
lines.append('};\n')
generated='\n'.join(lines)
path=root/'tests/pointer_shape_reference.h'
args=argparse.ArgumentParser();args.add_argument('--check',action='store_true');options=args.parse_args()
if options.check:
    assert path.read_text()==generated,'Regenerate pointer reference header'
else:
    path.write_text(generated,encoding='utf-8')
print(json.dumps(dict(cases=len(selected),stages=sum(len(c['steps']) for c in selected),
                      reserved_for_terminal_replay=excluded)))

lines=['/* Generated from unchanged independent upstream capture '+digest+'.',
       ' * All input chunks and pointer observations; no parser-policy adaptations. */',
       'static const PointerTerminalReference pointer_terminal_reference[] = {']
for case in data['cases']:
    for i,stage in enumerate(case['steps']):
        wire=base64.b64decode(stage['input_base64'],validate=True)
        reply=base64.b64decode(stage['reply_base64'],validate=True)
        chunks=stage['chunk_bytes']
        assert sum(chunks)==len(wire) and all(0<n<65536 for n in chunks)
        fields=[json.dumps(case['name']+'/'+stage['label']),str(int(i==0)),
                literal(wire),str(len(wire)),literal(reply),str(len(reply)),
                json.dumps(stage['current_shape']),
                '(const unsigned short[]){'+','.join(map(str,chunks))+'}',str(len(chunks))]
        lines.append('    {'+', '.join(fields)+'},')
lines.append('};\n')
generated='\n'.join(lines)
path=root/'tests/pointer_terminal_reference.h'
if options.check:
    assert path.read_text()==generated,'Regenerate terminal pointer reference header'
else:
    path.write_text(generated,encoding='utf-8')
print(json.dumps(dict(terminal_cases=len(data['cases']),terminal_stages=data['state_count'])))
