"""Generate exact colour-sequence replays from the retained independent XTerm capture."""
from pathlib import Path
import argparse, hashlib, json, tarfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
archive = root/'research/osc-colour-sequence-reference.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == 'a4fe4d8a5f098af8047a1fba548827b545e3488cb518962a11d740af12de9908'
with tarfile.open(archive) as bundle:
    data = json.load(bundle.extractfile('xterm.json'))
    identity = json.load(bundle.extractfile('IDENTITY.json'))
assert data['version'] == 'XTerm(412)' and len(data['cases']) == 72
assert data['executable_sha256'] == identity['executable_sha256']
assert identity['source_commit'] == '5c75ead9a75d4b2e666ca06fa94503b5766ed93f'
records, differences = [], []
for name, value in data['cases'].items():
    assert bytes.fromhex(value['reply_hex']).decode() == value['reply']
    record = dict(name=name, sequence=value['sequence'], reply_hex=value['reply_hex'])
    if name.endswith('-extra-rgb-component'):
        # Keep the existing exact three-component parser contract; do not
        # relabel Xlib's accepted prefix as a matching malformed-input case.
        differences.append(record)
    else:
        records.append(record)
assert len(records) == 64 and len(differences) == 8

def literal(value):
    raw = value.encode() if isinstance(value, str) else value
    return '"'+''.join(chr(c) if 32 <= c < 127 and c not in (34, 92) else f'\\{c:03o}' for c in raw)+'"'

header = '/* Generated from the retained XTerm capture. Do not edit. */\n'
header += 'static const struct { const char *name, *sequence, *reply; } osc_colour_sequence_reference[] = {\n'
for record in records:
    header += '    {'+', '.join((literal(record['name']), literal(record['sequence']),
                               literal(bytes.fromhex(record['reply_hex']))))+'},\n'
header += '};\n'
document = json.dumps(dict(reference_source=identity['source_commit'],
    policy_differences='Eight Xlib accepted-prefix cases retain the stricter three-component product syntax; excluded from unchanged replay, not counted as passes.',
    cases=records, observed_syntax_differences=differences), indent=2)+'\n'
for path, value in [(root/'tests/osc_colour_sequence_reference.h', header),
                    (root/'tests/osc_colour_sequence_reference.json', document)]:
    if args.check:
        assert path.read_text(encoding='utf-8') == value, path
    else:
        path.write_text(value, encoding='utf-8')
print('Verified' if args.check else 'Generated', '64 unchanged streams; eight syntax observations retained separately')
