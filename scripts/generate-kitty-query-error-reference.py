"""Generate literal captured query/error replies and complete-image state.

Every test uses displayed images only. Upstream empty pending/failed image slots
are retained separately from complete-image counts. Error descriptions remain
literal here; the data-error control compares the error envelope, not its prose.
"""
import argparse,base64,gzip,hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
raw=gzip.decompress((root/'research/kitty-query-errors-evidence/808974e-reference--observations.json.gz').read_bytes())
digest='2236da05d2fe7392f16d3f2486e2586ed1241ea08cf08270b62bba27a4f8fc62'
assert hashlib.sha256(raw).hexdigest()==digest
data=json.loads(raw)
assert data['status']=='complete' and (data['case_count'],data['state_count'])==(54,216)
assert data['upstream_commit']=='8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f'
def literal(raw):
 return '"'+''.join('\\%03o'%c if c<32 or c>=127 else '\\'+chr(c) if c in (34,92) else chr(c) for c in raw)+'"'
lines=[f'/* Literal capture SHA256 {digest}. Empty upstream slots are retained separately. */',
       'static const KittyFeatureReference kitty_query_error_reference[] = {']
native=[];excluded=0
for case in data['cases']:
 out=dict(name=case['name'],steps=[]);native.append(out)
 for i,step in enumerate(case['steps']):
  wire=base64.b64decode(step['input_base64']);reply=base64.b64decode(step['reply_base64'])
  boxes=[]
  for layer in step['layers']:
   d,s=layer['dest_rect'],layer['src_rect']
   values=[(d['left']+1)*60,(1-d['top'])*80,(d['right']+1)*60,(1-d['bottom'])*80,
           s['left'],s['top'],s['right'],s['bottom'],layer['z_index']]
   boxes.append('{'+','.join(f'{v:.9g}' for v in values)+'}')
  complete=len(boxes)
  assert 1<=complete<=2 and step['image_count']-complete in (0,1)
  excluded+=step['image_count']-complete
  fields=[json.dumps(case['name']+'/'+step['label']),literal(wire),literal(reply),literal(reply),
          str(int(i==0)),*map(str,step['cursor']),str(complete),str(step['image_count']),str(complete),
          '{'+','.join(boxes)+'}']
  lines.append('    {'+','.join(fields)+'},')
  out['steps'].append(dict(label=step['label'],input_base64=step['input_base64'],reply_base64=step['reply_base64'],
   complete_images=complete,upstream_images=step['image_count'],
   error_envelope_only=case['name']=='continuation-invalid-base64' and step['label']=='interleaved'))
assert excluded==109,excluded
lines.append('};\n')
targets=[(root/'vendor/putty-0.85/test/kitty_query_error_reference.h','\n'.join(lines).encode()),
 (root/'tests/kitty_query_error_reference.json',(json.dumps(dict(upstream_sha256=digest,cases=native),indent=2)+'\n').encode())]
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');check=p.parse_args().check
for path,content in targets:
 if check:assert path.read_bytes().replace(b'\r\n',b'\n')==content
 else:path.write_bytes(content)
print('Pinned query errors: 54 cases, 216 states; 109 empty upstream slots retained separately')
