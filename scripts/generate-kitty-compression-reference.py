"""Derive real terminal parser checks from the retained upstream compression capture."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import zlib

root = Path(__file__).resolve().parents[1]
codec = root/'vendor/putty-0.85/terminal/puff'
manifest = json.loads((codec/'SOURCE.json').read_text())
for entry in manifest['files']:
    assert hashlib.sha256((codec/entry['file']).read_bytes()).hexdigest() == entry['modified_sha256'], entry['file']
raw = gzip.decompress((root/'testdata/upstream/kitty-compression-evidence/257015d-reference--observations.json.gz').read_bytes())
digest = '6e6cb02704aaa748749759a7b991c67d39908ec12ab89acb6bfa536438c86321'
assert hashlib.sha256(raw).hexdigest() == digest
data = json.loads(raw)
assert data['status'] == 'complete' and data['case_count'] == 26 and data['state_count'] == 36
assert data['upstream_commit'] == '8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f'


def literal(raw):
    def part(chunk):
        return '"'+''.join('\\%03o'%c if c<32 or c>=127 else '\\'+chr(c) if c in (34,92) else chr(c) for c in chunk)+'"'
    return '\n        '.join(part(raw[i:i+384]) for i in range(0,len(raw),384)) or '""'


lines = ['/* Generated from independent capture SHA-256 '+digest+'.',
         ' * Original wire replies and decoded bytes remain in the raw capture.',
         ' * Error checks compare code/identity, not implementation-specific prose.',
         ' * Empty upstream internal slots are not counted as decoded images. */',
         'typedef struct KittyCompressionReference {',
         '    const char *name, *wire, *reply;',
         '    unsigned first, error_prefix, x, y, width, height;',
         '    const uint32_t *pixels;',
         '} KittyCompressionReference;']
pixel_sets = {}
entries = []
for case in data['cases']:
    for index, step in enumerate(case['steps']):
        wire = base64.b64decode(step['input_base64'])
        reply = base64.b64decode(step['reply_base64'])
        image = step['image']
        name = 'NULL'
        width = height = 0
        if image:
            decoded = base64.b64decode(image['data_base64'])
            assert hashlib.sha256(decoded).hexdigest() == image['data_sha256']
            width, height = image['width'], image['height']
            channels = len(decoded)//(width*height)
            assert channels in (3,4) and len(decoded) == width*height*channels
            if decoded not in pixel_sets:
                name = 'kitty_compression_pixels_'+str(len(pixel_sets))
                pixel_sets[decoded] = name
                values = []
                for i in range(0,len(decoded),channels):
                    r,g,b = decoded[i:i+3]
                    a = decoded[i+3] if channels == 4 else 255
                    values.append('0x%08xu'%((a<<24)|(r<<16)|(g<<8)|b))
                lines.append('static const uint32_t '+name+'[] = {\n    '+',\n    '.join(','.join(values[i:i+8]) for i in range(0,len(values),8))+'\n};')
            name = pixel_sets[decoded]
        if case['name'] == 'png-exact-size':
            encoded_png = zlib.decompress(base64.b64decode(wire.split(b';',1)[1][:-2]))
            lines += ['static const unsigned char kitty_compression_png[] = {',
                      '    '+','.join(str(x) for x in encoded_png)+'\n};',
                      '#define kitty_compression_png_pixels '+name,
                      '#define KITTY_COMPRESSION_PNG_WIDTH '+str(width),
                      '#define KITTY_COMPRESSION_PNG_HEIGHT '+str(height)]
        error = b';EINVAL:' in reply
        if error: reply = reply.partition(b':')[0]+b':'
        entries.append('    {'+','.join([json.dumps(case['name']+'/'+step['label']),literal(wire),literal(reply),
                       str(int(index==0)),str(int(error)),*map(str,step['cursor']),str(width),str(height),name])+'},')
lines += ['static const KittyCompressionReference kitty_compression_reference[] = {', *entries, '};\n']
expected = '\n'.join(lines).encode()
zlines = ['/* Byte pairs from the same independent Kitty compression capture. */',
          'typedef struct ZlibReference {',
          '    const unsigned char *encoded, *decoded;',
          '    size_t encoded_size, decoded_size;',
          '} ZlibReference;']
zentries = []
for case in data['cases'][:6]:
    step = case['steps'][0]
    wire = base64.b64decode(step['input_base64'])
    encoded = base64.b64decode(wire.split(b';',1)[1][:-2])
    decoded = base64.b64decode(step['image']['data_base64'])
    kind = {'stored':0, 'fixed':1, 'dynamic':2}[case['name'].split('-')[1]]
    assert (encoded[2]>>1)&3 == kind
    assert zlib.decompress(encoded) == decoded
    name = 'zlib_'+case['name'].replace('-','_')
    for suffix, raw in [('encoded',encoded),('decoded',decoded)]:
        zlines += ['static const unsigned char '+name+'_'+suffix+'[] = {',
                   '    '+',\n    '.join(','.join(str(v) for v in raw[i:i+24]) for i in range(0,len(raw),24)), '};']
    zentries.append('    {'+name+'_encoded,'+name+'_decoded,sizeof('+name+'_encoded),sizeof('+name+'_decoded)},')
zlines += ['static const ZlibReference zlib_reference[] = {',*zentries,'};\n']
targets = [(root/'vendor/putty-0.85/test/kitty_compression_reference.h',expected),
           (root/'tests/zlib_reference.h','\n'.join(zlines).encode())]
parser = argparse.ArgumentParser()
parser.add_argument('--check',action='store_true')
check = parser.parse_args().check
for target, content in targets:
    if check: assert target.read_bytes().replace(b'\r\n',b'\n') == content, target
    else: target.write_bytes(content)
if check:
    print('Pinned Kitty compression capture: 26 cases, 36 states and decoded pixels verified')
