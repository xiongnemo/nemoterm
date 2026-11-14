"""Generate exact UPSS parser expectations from the independent XTerm capture."""
import argparse,hashlib,json,re
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path)
args=p.parse_args();raw=args.capture.read_bytes();data=json.loads(raw)
assert data['executable_sha256']=='089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c'
def literal(data):
    return '"'+''.join(chr(c) if 32<=c<127 and c not in (34,92) else '\\%03o'%c for c in data)+'"'
out='/* Independent XTerm(412) UPSS capture. Source SHA-256: '+hashlib.sha256(raw).hexdigest()+' */\n'
out+='static const struct { const char *name, *input, *reply; } upss_reference[] = {\n'
cells=0
for name,case in data['cases'].items():
    response=bytes.fromhex(case['reply_hex'])
    if name.startswith('map-'):
        checks=re.findall(rb'\x1bP([0-9]+)!~([0-9A-Fa-f]{4})\x1b\\',response)
        assert [int(n) for n,v in checks]==list(range(1,97)),name
        cells+=len(checks)
    out+='    {'+json.dumps(name)+','+literal(bytes.fromhex(case['sequence_hex']))+','+literal(response)+'},\n'
out+='};\n'
(Path(__file__).resolve().parents[1]/'tests/upss_reference.h').write_text(out,newline='\n')
print(len(data['cases']),'UPSS streams,',cells,'independent output cells')
