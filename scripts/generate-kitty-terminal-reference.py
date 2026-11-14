"""Generate terminal replay inputs and literal observations from pinned kitty.

Long captured APCs are split into legal <=4096-character chunks, without
changing decoded data, headers, order or expected replies/cursor/layers.
"""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
raw = gzip.decompress((root / 'research/kitty-reference-evidence/bf03e11-observations.json.gz').read_bytes())
digest = '139b42639c4bba3be07dbeee02c0863374af1e0e1fd5d2a193828b0c934a8efd'
assert hashlib.sha256(raw).hexdigest() == digest
data = json.loads(raw)
assert data['status'] == 'complete'
assert data['upstream_commit'] == '8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f'
assert data['geometry'] == dict(columns=12, rows=8, cell_width=10, cell_height=20)
splits = 0


def chunks(match):
    global splits
    header, payload = match.groups()
    if len(payload) <= 4096:
        return match[0]
    splits += 1
    assert b'm=' not in header
    parts = [payload[i:i+4096] for i in range(0, len(payload), 4096)]
    return b''.join(b'\x1b_G' + (header+b',' if i == 0 else b'') +
                    (b'm=0;' if i == len(parts)-1 else b'm=1;') + p + b'\x1b\\'
                    for i, p in enumerate(parts))


def literal(raw):
    # Short adjacent literals also work with MSVC's individual-literal limit.
    def quote(part):
        return '"' + ''.join('\\%03o' % c if c < 32 or c >= 127 else
                             '\\' + chr(c) if c in (34, 92) else chr(c) for c in part) + '"'
    return '\n        '.join(quote(raw[i:i+512]) for i in range(0, len(raw), 512)) or '""'


lines = ['/* Generated from capture SHA-256 ' + digest + '.',
         ' * Expected states are literal upstream observations, not local calculations.',
         ' * Oversize APC payloads are only split into legal protocol chunks. */',
         'static const KittyTerminalReference kitty_terminal_reference[] = {']
for case in data['cases']:
    for index, step in enumerate(case['steps']):
        wire = re.sub(rb'\x1b_G([^;]*);([A-Za-z0-9+/=]+)\x1b\\', chunks,
                      base64.b64decode(step['input_base64']))
        layers = []
        assert len(step['layers']) <= 4
        for box, layer in zip(step['pixel_boxes'], step['layers']):
            values = [box[k] for k in ('left', 'top', 'right', 'bottom')]
            values += [layer['src_rect'][k] for k in ('left', 'top', 'right', 'bottom')]
            values.append(layer['z_index'])
            layers.append('{' + ','.join(map(repr, values)) + '}')
        if not layers:
            layers.append('{0}')
        fields = [json.dumps(case['name']+'/'+step['label']), str(int(index == 0)),
                  *map(str, case['start']), *map(str, step['cursor']),
                  str(step['image_count']), str(len(step['layers'])), str(step['layer_scrollback']),
                  literal(wire), literal(base64.b64decode(step['reply_base64'])),
                  '{'+','.join(layers)+'}']
        lines.append('    {' + ','.join(fields) + '},')
lines.append('};\n')
assert splits == 6
expected = '\n'.join(lines).encode()
target = root / 'vendor/putty-0.85/test/kitty_terminal_reference.h'
parser = argparse.ArgumentParser()
parser.add_argument('--check', action='store_true')
if parser.parse_args().check:
    assert target.read_bytes().replace(b'\r\n', b'\n') == expected
    print('Pinned kitty terminal replay: 101 states, 43 cases, 6 chunk-normalized inputs verified')
else:
    target.write_bytes(expected)
