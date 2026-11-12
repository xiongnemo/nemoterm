"""Replay independent margin cases against XTerm on a private Xvfb display."""
import argparse,json,re
from pathlib import Path
from xterm_state_oracle import run_cases
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--xterm',default='/tmp/nemoterm-xterm-reference/xterm')
parser.add_argument('--output',default=str(root/'research/margins-xterm.json'))
args=parser.parse_args()
source=json.loads((root/'research/margins-xterm.json').read_text())
run_cases(args.xterm,args.output,{k:v['sequence'] for k,v in source['cases'].items()},
          ['-ti','vt420','-xrm','*decGraphicsID: 340','-xrm','*allowWindowOps: true'])
path=Path(args.output);data=json.loads(path.read_text())
data['resources']=['-ti','vt420','-xrm','*decGraphicsID: 340','-xrm','*allowWindowOps: true']
for name,case in data['cases'].items():
    found=re.findall(r'\x1bP(\d+)!~([0-9a-fA-F]+)\x1b\\',case['reply'])
    assert len(found)==84,(name,len(found))
    case['rows']=[''.join(chr(int(v,16)) for _,v in found[i:i+12]) for i in range(0,84,12)]
    case['state_reply']=case['reply'].split('\x1bP1!~')[0]
    attrs=re.findall(r'\x1bP\d+!~[0-9a-fA-F]+\x1b\\\x1b\[([^m]*)m',case['reply'])
    if attrs:
        assert len(attrs)==84,(name,len(attrs))
        case['attrs']=attrs
path.write_text(json.dumps(data,indent=2))
