"""Copy unchanged input/reply bytes from the retained independent XTerm run."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
digest = 'd69f11e6a36383d0cd8e08c4555bc6decb67f063c751992cd640f77acc9c0fa1'
with tarfile.open(root/'testdata/upstream/control-cancellation-reference.tar.gz') as archive:
    raw = archive.extractfile('reference/control-cancellation-xterm.json').read()
assert hashlib.sha256(raw).hexdigest() == digest
data = json.loads(raw)
assert data['completed'] and len(data['cases']) == 254
assert sum(len(c['cells']) for c in data['cases'].values()) == 1960


def literal(value):
    return '"' + ''.join('\\%03o' % c if c < 32 or c >= 127 else
                         '\\' + chr(c) if c in (34, 92) else chr(c)
                         for c in value) + '"'


lines = ['/* Unchanged independent XTerm observations: ' + digest + '. */',
         'static const CancellationReference cancellation_reference[] = {']
for name, case in data['cases'].items():
    wire, reply = (bytes.fromhex(case[key]) for key in ('sequence_hex', 'reply_hex'))
    lines.append('    {' + ', '.join([json.dumps(name), literal(wire), str(len(wire)),
                                     literal(reply), str(len(reply))]) + '},')
lines.append('};\n')
generated = '\n'.join(lines)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
path = root/'tests/control_cancellation_reference.h'
if args.check:
    assert path.read_text(encoding='utf-8') == generated, 'Regenerate cancellation reference'
else:
    path.write_text(generated, encoding='utf-8')

# This projection is for the existing UTF-8 console-output fixture. Raw C1
# bytes and deliberately truncated UTF-8 remain in the complete core matrix.
native, excluded = [], []
for name, case in data['cases'].items():
    wire, reply = (bytes.fromhex(case[key]) for key in ('sequence_hex', 'reply_hex'))
    try:
        text = wire.decode('utf-8')
    except UnicodeDecodeError:
        excluded.append((name, 'non-UTF-8 input bytes'))
        continue
    assert text.encode('utf-8') == wire and all(c < 128 for c in reply)
    native.append((name, text, reply))
assert len(native) == 236 and len(excluded) == 18
projection = '# Generated from unchanged XTerm observations.\n'
projection += 'REFERENCE_SHA256 = ' + repr(digest) + '\n'
projection += 'CASES = ' + repr(native) + '\nEXCLUDED = ' + repr(excluded) + '\n'
path = root/'tests/control_cancellation_native_cases.py'
if args.check:
    assert path.read_text(encoding='utf-8') == projection, 'Regenerate native cancellation reference'
else:
    path.write_text(projection, encoding='utf-8')
print('254 unchanged XTerm streams; 1960 Unicode cell observations; 4 literal controls')
