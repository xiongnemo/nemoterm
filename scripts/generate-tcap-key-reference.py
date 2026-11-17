"""Project original hosted XKB events and bytes into a core keyboard fixture."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
archive = root/'research/terminfo-database-evidence.zip'
if hashlib.sha256(archive.read_bytes()).hexdigest() != '7e3270eadc8063fc85624e67dd3fae0ee26a654e8d82e37374c63199300d0df0':
    raise ValueError('Unexpected startup archive')
with zipfile.ZipFile(archive) as bundle:
    name = next(n for n in bundle.namelist() if n.startswith('44072174561/') and n.endswith('.selected.zip'))
    with zipfile.ZipFile(io.BytesIO(bundle.read(name))) as source:
        data = json.loads(source.read('terminfo-export/startup-keys.json'))
if not data['completed']:
    raise ValueError('Incomplete startup observations')


def literal(value):
    if isinstance(value, str):
        value = value.encode()
    return '"' + ''.join(chr(b) if 32 <= b < 127 and b not in (34, 92)
                         else f'\\{b:03o}' for b in value) + '"'


arrows = {0xff51:'D', 0xff52:'A', 0xff53:'C', 0xff54:'B'}
editing = {0xff50:'SKK_HOME', 0xff55:'SKK_PGUP', 0xff56:'SKK_PGDN',
           0xff57:'SKK_END', 0xff63:'SKK_INSERT', 0xffff:'SKK_DELETE'}
rows = []
for name, case in data['cases'].items():
    if not case['completed'] or case['exit_code'] != 0:
        raise ValueError('Incomplete startup case')
    for index, step in enumerate(case['steps']):
        events = [a for a in step['actions_observed'] if a['action'][0] == 'key'
                  and a['action'][2] and a['action'][1] not in ('Shift_L', 'Control_L', 'Alt_L')]
        if len(events) > 1:
            raise ValueError('Unexpected multi-key step')
        kind, code, resource, point, mods = 0, '0', 0, 0, 0
        if events:
            symbol, state = events[0]['keysym'], events[0]['state_before']
            if state & ~(1|4|8):
                raise ValueError('Unexpected lock/modifier state')
            mods = (1 if state & 1 else 0) | (2 if state & 8 else 0) | (4 if state & 4 else 0)
            if symbol in arrows:
                kind, code = 1, str(ord(arrows[symbol]))
            elif symbol in editing:
                kind, code = 2, editing[symbol]
            elif 0xffbe <= symbol <= 0xffe0:
                kind, code = 3, str(symbol-0xffbe+1)
            elif 0xff80 <= symbol <= 0xffbd:
                kind, resource, point = 4, 3, symbol-0x1d00
            elif symbol in (0xff08, 0xff09, 0xfe20):
                kind, resource, point = 4, 7, symbol-0xff00 if symbol >= 0xff00 else 0xe120
            else:
                raise ValueError('Unmapped observed symbol: ' + hex(symbol))
        # Only ASCII hex case in a capability response is normalized. Physical
        # input bytes (including ESC, letters and function-key finals) stay exact.
        reply = bytes.fromhex(step['reply_hex'])
        reply = re.sub(rb'(\x1bP[01]\+r[^\x1b]*)',
                       lambda m: re.sub(rb'=[0-9a-fA-F]*', lambda h: h[0].lower(), m[0]), reply)
        values = [literal(name), literal(case['selected_terminal']),
                  literal(bytes.fromhex(step['sequence_hex'])), literal(reply),
                  str(index == 0).lower(), str(kind), code, str(resource), str(point), str(mods)]
        rows.append('    {' + ', '.join(values) + '},')
if len(rows) != 1378:
    raise ValueError('Incomplete startup projection')
header = ('/* Original hosted XTerm bytes and observed XKB identities; no synthesized answers. */\n'
          'static const struct { const char *name, *terminal, *sequence, *reply; bool reset;\n'
          'unsigned kind; int code; unsigned resource, point, mods; } tcap_key_reference[] = {\n'
          + '\n'.join(rows) + '\n};\n')
target = root/'tests/tcap_key_reference.h'
if args.check:
    if target.read_text(encoding='utf-8') != header:
        raise ValueError('Stale startup projection')
else:
    target.write_text(header, encoding='utf-8')
print(('Verified' if args.check else 'Generated'), len(rows), 'startup steps')
