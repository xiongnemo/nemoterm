"""Project unchanged single-request replies from the independent XTerm capture.

Policy fixtures below are authored from the retained XTerm resource defaults,
operation enums and explicit profile resources, never inferred from replies.
This exercises the formatter; Nemo's actual permission mapping is tested by
test_feature_policy.c through the terminal parser separately.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile

root = Path(__file__).resolve().parents[1]
digest = '84990aadc68e758f926f703f279ceb52d039ed94f96d307465e46b6ac3b4e865'
with tarfile.open(root/'testdata/upstream/feature-policy-reference.tar.gz') as archive:
    raw = archive.extractfile('reference/feature-policy-xterm.json').read()
assert hashlib.sha256(raw).hexdigest() == digest
data = json.loads(raw)
assert data['completed'] and len(data['profiles']) == 20

categories = ['ColorOps', 'FontOps', 'MouseOps', 'PasteControls', 'TcapOps', 'TitleOps', 'WindowOps']
tables = [dict(SetColor=1, GetColor=2, GetAnsiColor=3), dict(SetFont=1, GetFont=2),
          dict(X10=1, Locator=2, VT200Click=3, VT200Hilite=4, AnyButton=5,
               AnyEvent=6, FocusEvent=7, Extended=8, SGR=9, URXVT=10, AlternateScroll=11),
          dict(zip('NUL SOH STX ETX EOT ENQ ACK BEL BS HT LF VT FF CR SO SI DLE DC1 DC2 DC3 DC4 NAK SYN ETB CAN EM SUB ESC FS GS RS US'.split(), range(32))),
          dict(SetTcap=1, GetTcap=2), {},
          dict(zip('RestoreWin MinimizeWin SetWinPosition SetWinSizePixels RaiseWin LowerWin RefreshWin SetWinSizeChars MaximizeWin FullscreenWin GetWinState GetWinPosition GetWinSizePixels GetWinSizeChars GetScreenSizeChars GetIconTitle GetWinTitle PushTitle PopTitle SetWinLines ColumnMode SetXprop GetSelection SetSelection GetChecksum SetChecksum'.split(),
                   [1,2,3,4,5,6,7,8,9,10,11,13,14,18,19,20,21,22,23,24,25,26,27,28,29,30]))]
tables[3].update(NL=10, C0=32, DEL=33, STTY=34)
defaults = ['SetColor,GetColor,GetAnsiColor', 'SetFont,GetFont', ','.join(tables[2]),
            'NUL,EOT,ENQ,BS,ESC,DEL,STTY', 'SetTcap,GetTcap', '',
            'GetIconTitle,GetWinTitle,SetXprop,GetSelection,SetSelection,GetChecksum']

def mask(table, names):
    return sum(1 << code for code in {table[name] for name in names if name})

def literal(value):
    return '"'+''.join('\\%03o'%b if b < 32 or b >= 127 else
                       '\\'+chr(b) if b in (34,92) else chr(b) for b in value)+'"'

lines = ['/* Original XTerm capture SHA256: '+digest+' */',
         'static const NemoFeaturePolicy feature_policies[] = {']
for profile in data['profiles'].values():
    assert profile['completed'] and not profile['forced_cleanup'] and profile['exit_code'] == 0
    resources = profile['resources']
    enabled = sum(1 << i for i, name in enumerate(categories)
                  if resources.get('allow'+name, 'false' if i in (3,6) else 'true') == 'true')
    supported = [mask(t, t) for t in tables]
    restricted = [mask(t, resources.get('disallowed'+name, defaults[i]).split(','))
                  for i, (name,t) in enumerate(zip(categories,tables))]
    fmt = lambda values: '{'+','.join('UINT64_C(%d)'%v for v in values)+'}'
    lines.append('    {%d,%s,%s},'%(enabled,fmt(supported),fmt(restricted)))
lines += ['};', 'static const FeatureReference feature_reference[] = {']
count = 0
for index, (name, profile) in enumerate(data['profiles'].items()):
    assert len(profile['cases']) == 105
    for case, capture in profile['cases'].items():
        wire = bytes.fromhex(capture['sequence_hex'])
        reply = bytes.fromhex(capture['reply_hex'])
        assert bytes.fromhex(capture['wire_with_barrier_hex']) == reply+b'\x1b[0n'
        match = re.fullmatch(rb'\x1b\](\d+)(?:;([^\x1b\x07]*))?(\x07|\x1b\\)', wire)
        if not match:
            continue  # Compound/lifecycle/parser cases remain in the raw archive.
        number, payload, ending = match.groups()
        payload = payload or b''
        fields = [json.dumps(name+'/'+case), str(index), str(int(number)),
                  literal(payload), str(len(payload)), str(ending == b'\x07').lower(),
                  literal(reply), str(len(reply))]
        lines.append('    {'+', '.join(fields)+'},')
        count += 1
lines += ['};','']
assert count == 1780, count
text = '\n'.join(lines)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check',action='store_true')
args = parser.parse_args()
path = root/'tests/feature_policy_reference.h'
if args.check:
    assert path.read_text(encoding='utf-8') == text
else:
    path.write_text(text,encoding='utf-8')
print('Feature policy formatter: 20 source-derived policies / 1780 original replies')
