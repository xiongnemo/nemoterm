"""Project original bell-mode bytes and observed X11 state without changing them."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
digest = 'c5a87d9f9ee75d637293e3a6767d86102be622271720e8ee4b704e5727c9b6b4'
with tarfile.open(root/'research/bell-modes-reference.tar.gz') as archive:
    raw = archive.extractfile('reference/bell-modes-xterm.json').read()
assert hashlib.sha256(raw).hexdigest() == digest
data = json.loads(raw)
assert data['completed'] and len(data['cases']) == 112

def literal(raw):
    return '"'+''.join('\\%03o'%b if b < 32 or b >= 127 else
                       '\\'+chr(b) if b in (34,92) else chr(b) for b in raw)+'"'

lines = ['/* Original XTerm bell capture SHA256: '+digest+' */',
         'static const BellReference bell_reference[] = {']
steps = 0
for name,case in data['cases'].items():
    assert case['completed'] and case['exit_code'] == 0
    for index,step in enumerate(case['steps']):
        wire,reply = (bytes.fromhex(step[key]) for key in ('sequence_hex','reply_hex'))
        assert bytes.fromhex(step['wire_with_barrier_hex']) == reply+b'\x1b[0n'
        fields = [json.dumps(name+'/'+str(index)),str(index == 0).lower(),
                  str(name[0]=='1').lower(),str(name[1]=='1').lower(),
                  literal(wire),str(len(wire)),literal(reply),str(len(reply)),
                  str({'term':1,'other':0,None:-1}[step['focus']]),str(step['cover']).lower()]
        for key in ('window_before','window_after'):
            fields += [str(step[key][f]).lower() for f in ('urgency','above_other','term_focused')]
        lines.append('    {'+', '.join(fields)+'},')
        steps += 1
assert steps == 192
lines += ['};','']
text = '\n'.join(lines)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check',action='store_true')
args = parser.parse_args()
path = root/'tests/bell_modes_reference.h'
if args.check: assert path.read_text(encoding='utf-8') == text
else: path.write_text(text,encoding='utf-8')
print('Bell modes: 112 cases / 192 original reply streams and window states')
