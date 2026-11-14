"""Generate legacy/Unicode checksum arrays from independent XTerm observations."""
import argparse
import hashlib
import json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path)
p.add_argument('--lifetime',type=Path);a=p.parse_args()
raw=a.capture.read_bytes();data=json.loads(raw)
assert data['executable_sha256']=='089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c'
def literal(data):
    return '"'+''.join(chr(c) if 32<=c<127 and c not in (34,92) else '\\%03o'%c for c in data)+'"'
out='/* Independent XTerm(412) capture SHA-256: '+hashlib.sha256(raw).hexdigest()+' */\n'
out+='static const struct { const char *name, *setup; bool right; uint16_t sums[2][96]; } charset_checksum_reference[] = {\n'
for name,row in data['cases'].items():
    out+='    {'+json.dumps(name)+','+literal(bytes.fromhex(row['setup_hex']))+','+str(row['right']).lower()+',{\n'
    for mode in ('legacy','unicode'):
        assert len(row[mode])==96
        out+='        {'+','.join(f'0x{n:04x}' for n in row[mode])+'},\n'
    out+='    }},\n'
out+='};\n'
if a.lifetime:
    raw_lifetime=a.lifetime.read_bytes();lifetime=json.loads(raw_lifetime)
    assert lifetime['executable_sha256']==data['executable_sha256']
    out+='/* Independent lifetime capture SHA-256: '+hashlib.sha256(raw_lifetime).hexdigest()+' */\n'
    out+='static const struct { const char *name, *input, *reply; } charset_checksum_lifetime[] = {\n'
    for name,row in lifetime['cases'].items():
        out+='    {'+json.dumps(name)+','+literal(bytes.fromhex(row['sequence_hex']))+','+literal(bytes.fromhex(row['reply_hex']))+'},\n'
    out+='};\n'
(Path(__file__).resolve().parents[1]/'tests/charset_checksum_reference.h').write_text(out,newline='\n')
print(len(data['cases']),'streams;',len(data['cases'])*192,'independent cell checksums')
