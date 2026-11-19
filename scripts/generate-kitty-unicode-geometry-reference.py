"""Export independently captured cell-image rectangles for native pixel tests."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

root=Path(__file__).resolve().parents[1]
digest='c6a03613d5f5df5313ee7f07610bb4ac2b0615428a9ab5efd61f9fd06e59656a'
with tarfile.open(root/'testdata/upstream/kitty-unicode-evidence/font-geometry-reference.tar.gz') as tar:
    raw=tar.extractfile('reference/observations.json').read()
assert hashlib.sha256(raw).hexdigest()==digest
data=json.loads(raw)
assert data['status']=='complete' and data['case_count']==data['state_count']==153
assert data['upstream_commit']=='8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f'
reply=data['cases'][0]['reply_base64']
assert all(c['reply_base64']==reply for c in data['cases'])
result=dict(source_sha256=digest,input_base64=data['input_base64'],reply_base64=reply,cases={})
for case in data['cases']:
    assert case['image_count']==2 and case['cursor']==[0,0]
    record=dict(name=case['name'],layers=[])
    assert set(layer['image_id'] for layer in case['layers'])=={1,2}
    for layer in case['layers']:
        dest=layer['dest_rect']
        xs=case['columns']*case['cell_width']/2
        ys=case['rows']*case['cell_height']/2
        raw_pixels=[(dest['left']+1)*xs,(1-dest['top'])*ys,(dest['right']+1)*xs,(1-dest['bottom'])*ys]
        # Cell anchors and offsets are integral. Remove only NDC float noise,
        # with a checked maximum error, before native integer-pixel probes.
        pixels=list(map(round,raw_pixels))
        assert all(abs(a-b)<.001 for a,b in zip(raw_pixels,pixels))
        assert layer['z_index']==-1 and pixels[2]>pixels[0] and pixels[3]>pixels[1]
        record['layers'].append(dict(image_id=layer['image_id'],src_rect=layer['src_rect'],pixels=pixels))
    result['cases'][case['name']]=record
assert len(result['cases'])==153
text=json.dumps(result,indent=2)+'\n'
parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
path=root/'tests/kitty_unicode_geometry_reference.json'
if args.check:assert path.read_text()==text
else:path.write_text(text)
print('Verified 153 independently captured font-cell image geometries')
