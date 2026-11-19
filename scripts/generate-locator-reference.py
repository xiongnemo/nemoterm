"""Project unchanged XTerm Locator replies and observed pointer input into C."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
digest = 'fa3f3f13dd56847c093c8b638f8e658a8227bf29964485c63a07029bcb2fa96e'
with tarfile.open(root/'testdata/upstream/dec-locator-binding-reference.tar.gz') as archive:
    raw = archive.extractfile('bbddb98/reference/dec-locator-xterm.json').read()
assert hashlib.sha256(raw).hexdigest() == digest
data = json.loads(raw)
assert data['completed'] and len(data['cases']) == 102


def literal(value):
    return '"' + ''.join('\\%03o' % c if c < 32 or c >= 127 else
                         '\\' + chr(c) if c in (34, 92) else chr(c)
                         for c in value) + '"'


lines = ['/* Unchanged independent XTerm replies: '+digest+'. */']
rows = []
steps = intercepted = 0
for name, case in data['cases'].items():
    assert case['completed'] and case['exit_code'] == 0 and case['cell_pixels'] == [6, 13]
    assert case['initial_pointer']['pointer'] == dict(present=True, x=71, y=86, mask=0)
    explicit = bool(case['extra_resource_args'])
    for index, step in enumerate(case['steps']):
        actions = []
        assert len(step['actions']) == len(step['actions_observed'])
        for action, observed in zip(step['actions'], step['actions_observed'], strict=True):
            assert action == observed['action']
            p = observed['pointer']
            assert p['present']
            kind = {'key': 0, 'move': 1, 'pixel': 1, 'button': 2}[action[0]]
            button = action[1] if kind == 2 else 0
            press = action[2] if kind == 2 else 0
            # Retain the frontend dispatch boundary explicitly. XTerm's
            # default translations consume Ctrl button events and wheel down
            # events before SendLocatorPosition; named profiles override them.
            consumed = kind == 2 and not explicit and (
                bool(p['mask'] & 4) or (button >= 4 and press))
            intercepted += consumed
            actions.append('{%d,%d,%d,%d,%d,%du,%s}' % (
                kind, button, press, p['x'], p['y'], p['mask'], str(consumed).lower()))
        action_name = f'locator_actions_{steps}'
        if actions:
            lines.append('static const LocatorAction '+action_name+'[] = {'+','.join(actions)+'};')
        wire, reply = (bytes.fromhex(step[key]) for key in ('sequence_hex', 'reply_hex'))
        rows.append('    {'+', '.join((json.dumps(name+'/'+str(index)), str(index == 0).lower(),
            literal(wire), str(len(wire)), literal(reply), str(len(reply)),
            action_name if actions else 'NULL', str(len(actions))))+'},')
        steps += 1
assert steps == 429
lines += ['static const LocatorReference locator_reference[] = {', *rows, '};\n']
text = '\n'.join(lines)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
path = root/'tests/locator_reference.h'
if args.check:
    assert path.read_text(encoding='utf-8') == text, 'Regenerate Locator reference'
else:
    path.write_text(text, encoding='utf-8')
print(f'102 cases, {steps} unchanged reply streams; {intercepted} explicit upstream binding interceptions')
