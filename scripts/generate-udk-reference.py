"""Project original XTerm UDK bytes and key gestures without changing replies."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
digest = 'b6917d91165d635fc7d202be432028faa27104fc62e947ddc4d48c046c2dada3'
with tarfile.open(root/'research/dec-udk-reference.tar.gz') as archive:
    raw = archive.extractfile('9b798e2/reference/dec-udk-xterm.json').read()
assert hashlib.sha256(raw).hexdigest() == digest
data = json.loads(raw)
assert data['completed'] and len(data['cases']) == 91

def literal(raw):
    return '"'+''.join('\\%03o'%b if b < 32 or b >= 127 else
                       '\\'+chr(b) if b in (34,92) else chr(b) for b in raw)+'"'

lines = ['/* Original XTerm UDK capture SHA256: '+digest+' */',
         'static const UdkReference udk_reference[] = {']
steps = 0
for name, case in data['cases'].items():
    assert case['completed'] and case['exit_code'] == 0
    for index, step in enumerate(case['steps']):
        assert step['actions'] == [a['action'] for a in step['actions_observed']]
        modifiers, pressed, events = set(), None, []
        for kind,key,down in step['actions']:
            assert kind == 'key'
            if key.startswith('F'):
                if down:
                    assert pressed is None
                    pressed = key
                    events.append((int(key[1:]), sum(bit for mod,bit in
                        [('Shift_L',1),('Control_L',2),('Alt_L',4)] if mod in modifiers)))
                else:
                    assert pressed == key
                    pressed = None
            elif down: modifiers.add(key)
            else: modifiers.remove(key)
        assert not modifiers and pressed is None and len(events) <= 1
        key, mods = events[0] if events else (0,0)
        wire, reply = (bytes.fromhex(step[field]) for field in ('sequence_hex','reply_hex'))
        full = bytes.fromhex(step['wire_with_barriers_hex'])
        assert full.count(b'\x1b[0n') == 2 and full.replace(b'\x1b[0n',b'') == reply
        lines.append('    {'+', '.join([json.dumps(name+'/'+str(index)), str(index == 0).lower(),
            'FUNKY_VT220' if case['profile'] == 'vt220' else 'FUNKY_XTERM_216',
            literal(wire), str(len(wire)), literal(reply), str(len(reply)), str(key), str(mods)])+'},')
        steps += 1
assert steps == 238
lines += ['};','']
text = '\n'.join(lines)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check',action='store_true')
args = parser.parse_args()
path = root/'tests/udk_reference.h'
if args.check: assert path.read_text(encoding='utf-8') == text
else: path.write_text(text,encoding='utf-8')
print('UDK: 91 cases, 238 unchanged reply streams and physical key projections')
