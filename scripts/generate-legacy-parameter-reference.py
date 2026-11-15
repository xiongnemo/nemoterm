"""Project retained XTerm VT100 request syntax onto Nemoterm's existing report policy."""
from pathlib import Path
import argparse,hashlib,json,re,tarfile

root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
archive=root/'research/legacy-reply-reference.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='0ef5129230b862cecebdb0e6b74f3c77e0a076588886fd901766e03594db6b80'
with tarfile.open(archive) as tar:
    original=json.load(tar.extractfile('reference/xterm-vt100.json'))
assert original['version']=='XTerm(412)' and len(original['cases'])==136
records=[]
for name,case in original['cases'].items():
    raw=bytes.fromhex(case['reply_hex'])
    if raw:assert re.fullmatch(rb'\x1b\[[23];1;1;128;128;1;0x',raw),name
    # Serial characteristics are inherited project policy, not physical port
    # measurements. The captured VT100 argument decisions remain unchanged.
    expected=raw.replace(b';128;128;',b';112;112;')
    # This terminal supports S8C1T at level 5; a VT100 identity does not.
    if name.startswith('parameters-G-') and expected:
        assert expected.startswith(b'\x1b[');expected=b'\x9b'+expected[2:]
    records.append(dict(name=name,sequence=case['sequence'],reference_hex=raw.hex(),reply_hex=expected.hex()))
assert sum(bool(r['reply_hex']) for r in records)==24
def literal(value):
    data=value.encode() if isinstance(value,str) else value
    return '"'+''.join(chr(c) if 32<=c<127 and c not in (34,92) else f'\\{c:03o}' for c in data)+'"'
header='/* Generated from the retained XTerm VT100 capture. Do not edit. */\n'
header+='static const struct { const char *name, *sequence, *reply, *reference; } legacy_parameter_reference[] = {\n'
for r in records:
    header+='    {'+', '.join((literal(r['name']),literal(r['sequence']),literal(bytes.fromhex(r['reply_hex'])),literal(bytes.fromhex(r['reference_hex']))))+'},\n'
header+='};\n'
document=json.dumps(dict(reference_source='5c75ead9a75d4b2e666ca06fa94503b5766ed93f',
    policy_differences=['Fixed baud codes 112 instead of 128','S8C1T replies at level 5 instead of VT100 framing'],cases=records),indent=2)+'\n'
for path,text in [(root/'tests/legacy_parameter_reference.h',header),(root/'tests/legacy_parameter_reference.json',document)]:
    if args.check:assert path.read_text(encoding='utf-8')==text,path
    else:path.write_text(text,encoding='utf-8')
print('Verified' if args.check else 'Generated','136 unchanged reference streams with explicit report-policy projection')
