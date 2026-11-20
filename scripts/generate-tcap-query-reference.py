"""Project retained upstream query records into C source; never run a terminal."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
archive = root/'testdata/upstream/tcap-query-reference.zip'
if hashlib.sha256(archive.read_bytes()).hexdigest() != '6ebcafe5f675b49e24803369be4c51b5da9ac4914861e5ba45946e9188bb9e3d':
    raise ValueError('Unexpected reference archive')
with zipfile.ZipFile(archive) as source:
    data = json.loads(source.read('xterm.json'))
    identity = json.loads(source.read('IDENTITY.json'))
if not data['completed'] or data['executable_sha256'] != identity['executable_sha256']:
    raise ValueError('Incomplete or mismatched upstream observation')


def literal(value):
    if isinstance(value, str):
        value = value.encode()
    return '"' + ''.join(chr(b) if 32 <= b < 127 and b not in (34, 92)
                         else f'\\{b:03o}' for b in value) + '"'


rows = []
for case in data['cases'].values():
    if not case['completed'] or case['exit_code'] != 0:
        raise ValueError('Incomplete case')
    for step in case['steps']:
        if 'requested_capability' not in step:
            continue  # Independent physical-key mechanism controls, not queries.
        reply = bytes.fromhex(step['reply_hex'])
        rows.append('    {' + ', '.join(map(literal, (
            case['selected_terminal'], step['requested_capability'],
            bytes.fromhex(step['sequence_hex']), reply))) + '},')
if len(rows) != 2180:
    raise ValueError('Incomplete individual-query projection')
header = ('/* Exact wire bytes from retained XTerm queries and replies. */\n'
          'static const struct { const char *terminal, *capability, *query, *reply; }\n'
          'tcap_query_reference[] = {\n' + '\n'.join(rows) + '\n};\n')
target = root/'tests/tcap_query_reference.h'
if args.check:
    if target.read_text(encoding='utf-8') != header:
        raise ValueError('Stale query projection')
else:
    target.write_text(header, encoding='utf-8')
print(('Verified' if args.check else 'Generated'), len(rows), 'individual queries')
