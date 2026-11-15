"""Retain observed feature-query replies, with explicit unsupported-key omissions.

This is a projection of captured replies onto Nemoterm's existing capability
subset, not a second implementation of a feature-query responder. Every omitted
field is named per captured case below; no response fields are invented.
"""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
raw = gzip.decompress((root / 'research/kitty-feature-query-evidence/6ba7345-reference--observations.json.gz').read_bytes())
digest = 'd3e775257cfcf70308d88030f2b0bbee5f81a860b15eae4d9911a4ea2dc227ac'
assert hashlib.sha256(raw).hexdigest() == digest
capture = json.loads(raw)
assert capture['status'] == 'complete' and capture['case_count'] == 84 and capture['state_count'] == 176
assert capture['upstream_commit'] == '8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f'

# Unimplemented file offsets, transient hints, indexed images and animation
# remain omitted. Axis <=8192, encoded data <=2 MiB. Unicode/relative placement
# fields now retain the original captured replies after their implementation.
omit = {
    'action-f': 'e', 'action-a': 'e', 'action-c': 'e',
    'action-keys-t': 'ON', 'action-keys-T': 'ON', 'action-keys-q': 'ON',
    'action-keys-f': 'etofsvSONxycrzXY',
    'action-keys-a': 'esvrcz', 'action-keys-c': 'ercxywhXYC',
    'format-8': 'f', 'format-16': 'f',
    'medium-f': 't', 'medium-t': 't', 'medium-s': 't',
    'flag-N-1': 'N', 'dimensions-10000': 'sv',
    'unsigned-limits': 'SO', 'delete-F': 'd',
}


def literal(data):
    def chunk(part):
        return '"' + ''.join('\\%03o' % c if c < 32 or c >= 127 else
                             '\\' + chr(c) if c in (34, 92) else chr(c) for c in part) + '"'
    return '\n        '.join(chunk(data[i:i+256]) for i in range(0, len(data), 256)) or '""'


lines = [f'/* Captured upstream replies: SHA256 {digest}.',
         ' * Unsupported capabilities are explicitly omitted by the generator;',
         ' * original replies remain alongside projected product expectations. */',
         f'enum {{ KITTY_FEATURE_SUBSET_CASES = {len(omit)} }};',
         'typedef struct KittyFeatureReference {',
         '    const char *name, *wire, *reply, *upstream_reply;',
         '    unsigned first, x, y, images, upstream_images, layers;',
         '    double boxes[2][9];',
         '} KittyFeatureReference;',
         'static const KittyFeatureReference kitty_feature_reference[] = {']
seen = set()
native_cases = []
for case in capture['cases']:
    native_case = dict(name=case['name'], steps=[])
    native_cases.append(native_case)
    for index, step in enumerate(case['steps']):
        wire = base64.b64decode(step['input_base64'])
        original = reply = base64.b64decode(step['reply_base64'])
        if index == 1 and case['name'] in omit:
            fields, status = reply[3:].split(b';', 1)
            fields = fields.split(b',')
            removal = set(omit[case['name']])
            assert removal <= {field[:1].decode() for field in fields}, case['name']
            reply = b'\x1b_G' + b','.join(f for f in fields if f[:1].decode() not in removal) + b';' + status
            seen.add(case['name'])
        boxes = []
        for layer in step['layers']:
            d, s = layer['dest_rect'], layer['src_rect']
            values = [(d['left']+1)*60, (1-d['top'])*80,
                      (d['right']+1)*60, (1-d['bottom'])*80,
                      s['left'], s['top'], s['right'], s['bottom'], layer['z_index']]
            boxes.append('{' + ','.join(f'{v:.9g}' for v in values) + '}')
        assert len(boxes) <= 2
        # Upstream registers an empty internal image slot on the first chunk.
        # Nemoterm admits an image only on completed decode. Retain the original
        # count and compare complete images; no pending pixels/layers exist yet.
        pending = case['name'].startswith('pending-') and step['label'] in ('first-chunk', 'query')
        fields = [json.dumps(case['name']+'/'+step['label']), literal(wire),
                  literal(reply), literal(original), str(int(index == 0)),
                  *map(str, step['cursor']), str(step['image_count']-int(pending)),
                  str(step['image_count']), str(len(boxes)),
                  '{' + ','.join(boxes or ['{0}']) + '}']
        lines.append('    {' + ','.join(fields) + '},')
        native_case['steps'].append(dict(label=step['label'], input_base64=step['input_base64'],
            reply_base64=base64.b64encode(reply).decode(), upstream_reply_base64=step['reply_base64']))
assert seen == set(omit)
lines.append('};\n')
content = '\n'.join(lines).encode()
targets = [(root / 'vendor/putty-0.85/test/kitty_feature_reference.h', content),
           (root / 'tests/kitty_feature_reference.json',
            (json.dumps(dict(upstream_sha256=digest, subset_case_count=len(omit), cases=native_cases), indent=2)+'\n').encode())]
parser = argparse.ArgumentParser()
parser.add_argument('--check', action='store_true')
check = parser.parse_args().check
for target, content in targets:
    if check:
        assert target.read_bytes().replace(b'\r\n', b'\n') == content
    else:
        target.write_bytes(content)
print(f'Pinned Kitty feature queries: 84 cases, 176 states; {len(omit)} explicit subset projections')
