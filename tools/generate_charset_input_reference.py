"""Generate paste bytes captured from the isolated XTerm reference."""
import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path)
p.add_argument('--prefix',choices=('charset_input','upss_input'),default='charset_input')
args=p.parse_args();raw=args.capture.read_bytes();data=json.loads(raw)
assert data['executable_sha256']=='089de40f5a47b2ee07ddb778e7e031116673c7c20a55facbd9caf8d78978573c'
assert not data['keys']
def literal(data):
    return '"'+''.join(chr(c) if 32<=c<127 and c not in (34,92) else '\\%03o'%c for c in data)+'"'
out='/* Independent XTerm(412) selection-input capture. Source SHA-256: '+hashlib.sha256(raw).hexdigest()+' */\n'
out+='static const uint32_t '+args.prefix+'_text[] = {\n'
values=[ord(c) for c in data['text']]
for i in range(0,len(values),12):out+='    '+','.join(f'0x{x:x}' for x in values[i:i+12])+',\n'
out+='};\nstatic const CharsetInputCase '+args.prefix+'_reference[] = {\n'
for name,case in data['cases'].items():
    reply=bytes.fromhex(case['paste_hex'])
    out+='    {'+json.dumps(name)+','+literal(case['setup'].encode())+','+literal(reply)+','+str(len(reply))+'},\n'
out+='};\n'
(Path(__file__).resolve().parents[1]/('tests/'+args.prefix+'_reference.h')).write_text(out,newline='\n')
print(len(values),'codepoints,',len(data['cases']),'reference selections')
