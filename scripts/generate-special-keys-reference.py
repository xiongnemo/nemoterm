"""Project unchanged key/reply observations from a SHA-pinned XTerm capture."""
from pathlib import Path
import argparse, hashlib, json, tarfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
archive = root/'research/special-key-modifiers-reference.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == '89c9d0b4d2d88852ec937ce9d2efc89b6acd8f7b4b1e0d3ad6ee430e75944be6'
with tarfile.open(archive) as bundle:
    data = json.load(bundle.extractfile('capture-04/xterm.json'))
    identity = json.load(bundle.extractfile('capture-04/IDENTITY.json'))
assert data['completed'] and data['version'] == 'XTerm(412)' and len(data['cases']) == 81
assert identity['source_commit'] == '5c75ead9a75d4b2e666ca06fa94503b5766ed93f'
assert identity['executable_sha256'] == data['executable_sha256']

keys = {'Up': (1, "'A'", 38, 0x148), 'Down': (1, "'B'", 40, 0x150),
        'Right': (1, "'C'", 39, 0x14d), 'Left': (1, "'D'", 37, 0x14b),
        'Home': (3, 'SKK_HOME', 36, 0x147), 'End': (3, 'SKK_END', 35, 0x14f),
        'Insert': (3, 'SKK_INSERT', 45, 0x152), 'Delete': (3, 'SKK_DELETE', 46, 0x153),
        'Prior': (3, 'SKK_PGUP', 33, 0x149), 'Next': (3, 'SKK_PGDN', 34, 0x151)}
for number in (1, 5, 12, 20):
    keys['F'+str(number)] = (2, str(number), 111+number,
                             {1: 0x3b, 5: 0x3f, 12: 0x58, 20: 0x6b}[number])
records, differences = [], []
for name, case in data['cases'].items():
    assert case['completed'] and case['exit_code'] == 0
    for index, step in enumerate(case['steps']):
        record = dict(name=name, index=index, reset=index == 0, sequence_hex=step['sequence_hex'],
                      reply_hex=step['reply_hex'], key=step['key'], mods=step['modifiers'])
        if name == 'state-reset-all':
            differences.append(record)
            continue
        kind, code, vk, scan = keys[step['key']] if step['key'] else (0, '0', 0, 0)
        before, after, tail = bytes.fromhex(step['wire_with_barriers_hex']).split(b'\x1b[0n')
        assert not tail and (before+after).hex() == step['reply_hex']
        record.update(kind=kind, code=code, vk=vk, scan=scan,
                      before_reply_hex=before.hex(), key_reply_hex=after.hex())
        records.append(record)
assert len(records) == 394 and len(differences) == 1

def literal(raw):
    if isinstance(raw, str): raw = raw.encode()
    return '"'+''.join(chr(c) if 32 <= c < 127 and c not in (34, 92) else f'\\{c:03o}' for c in raw)+'"'

header = '/* Generated from unchanged pinned XTerm observations. Do not edit. */\n'
header += 'struct special_key_reference { const char *name, *sequence, *reply; int kind, key, mods; bool reset; };\n'
header += 'static const struct special_key_reference special_keys_reference[] = {\n'
for r in records:
    header += '    {'+', '.join([literal(r['name']), literal(bytes.fromhex(r['sequence_hex'])),
        literal(bytes.fromhex(r['reply_hex'])), str(r['kind']), r['code'], str(r['mods']),
        'true' if r['reset'] else 'false'])+'},\n'
header += '};\n'
document = json.dumps(dict(reference_source=identity['source_commit'], cases=records,
    policy_difference='Reset-all uses the documented all-resources contract; the one differing observation is retained separately, not counted as parity.',
    observed_policy_differences=differences), indent=2)+'\n'
for path, value in [(root/'tests/special_keys_reference.h', header),
                    (root/'tests/special_keys_reference.json', document)]:
    if args.check: assert path.read_text(encoding='utf-8') == value, path
    else: path.write_text(value, encoding='utf-8')
print('Verified' if args.check else 'Generated', '394 unchanged steps; one documented reset-policy difference')
