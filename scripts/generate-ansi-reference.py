"""Project unchanged wire observations from the retained pinned XTerm capture."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
digest = '098028b29c4cbfe4ea66a447e576ddd3750baa9acafe270697ab9194d4c23506'
with tarfile.open(root / 'testdata/upstream/ansi-conformance-reference.tar.gz') as archive:
    raw = archive.extractfile('3b49cd4/reference/ansi-conformance-xterm.json').read()
assert hashlib.sha256(raw).hexdigest() == digest
data = json.loads(raw)
assert data['completed'] and len(data['cases']) == 243
assert sum(c['cell_count'] for c in data['cases'].values()) == 1443


def literal(value):
    return '"' + ''.join('\\%03o' % c if c < 32 or c >= 127 else
                         '\\' + chr(c) if c in (34, 92) else chr(c)
                         for c in value) + '"'


lines = ['/* Generated from unchanged XTerm observations: ' + digest + '. */',
         'static const AnsiReference ansi_reference[] = {']
for name, case in data['cases'].items():
    wire, reply = (bytes.fromhex(case[key]) for key in ('sequence_hex', 'reply_hex'))
    lines.append('    {' + ', '.join([json.dumps(name), literal(wire), str(len(wire)),
                                     literal(reply), str(len(reply))]) + '},')
lines.append('};\n')
generated = '\n'.join(lines)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
path = root / 'tests/ansi_conformance_reference.h'
if args.check:
    assert path.read_text(encoding='utf-8') == generated, 'Regenerate ANSI conformance reference'
else:
    path.write_text(generated, encoding='utf-8')

# The native console fixture writes UTF-8 text. Keep only losslessly encodable
# streams with seven-bit replies, and name every omitted binary-only case.
native, excluded = [], []
for name, case in data['cases'].items():
    wire, reply = (bytes.fromhex(case[key]) for key in ('sequence_hex', 'reply_hex'))
    try:
        text = wire.decode('utf-8')
    except UnicodeDecodeError:
        excluded.append((name, 'non-UTF-8 input bytes'))
        continue
    if any(c >= 128 for c in reply):
        excluded.append((name, 'eight-bit reply framing'))
        continue
    assert text.encode('utf-8') == wire
    native.append((name, text, reply))
assert len(native) == 177 and len(excluded) == 66
projection = '# Generated from unchanged XTerm observations.\n'
projection += 'REFERENCE_SHA256 = ' + repr(digest) + '\n'
projection += 'CASES = ' + repr(native) + '\nEXCLUDED = ' + repr(excluded) + '\n'
path = root/'tests/ansi_conformance_native_cases.py'
if args.check:
    assert path.read_text(encoding='utf-8') == projection, 'Regenerate native ANSI reference'
else:
    path.write_text(projection, encoding='utf-8')
print('243 unchanged XTerm streams; 1443 Unicode cell observations; 3 literal controls')
