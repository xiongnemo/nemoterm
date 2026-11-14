"""Generate exact parser transition cases from an independently retained capture."""
import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path)
args=p.parse_args();raw=args.capture.read_bytes();data=json.loads(raw)
assert data['executable_sha256']=='089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c'
def literal(data):
    return '"'+''.join(chr(c) if 32<=c<127 and c not in (34,92) else '\\%03o'%c for c in data)+'"'
out='/* Independent XTerm(412) isolated state captures. Source SHA-256: '+hashlib.sha256(raw).hexdigest()+' */\n'
out+='static const struct { const char *name, *input, *reply; } charset_state_reference[] = {\n'
for name,case in data['cases'].items():
    out+='    {'+json.dumps(name)+','+literal(bytes.fromhex(case['sequence_hex']))+','+literal(bytes.fromhex(case['reply_hex']))+'},\n'
out+='};\n'
(Path(__file__).resolve().parents[1]/'tests/charset_state_reference.h').write_text(out,newline='\n')
