"""Collect all 26 cells of an edited row; retain raw XTerm replies and input."""
import argparse
import json
from pathlib import Path
import re

ESC='\x1b'; CSI=ESC+'['

def scenes():
    # Zero-based values match the GUI fixtures. Set LR margins only after
    # drawing the whole row, and remove them before absolute checksum queries.
    shapes=[('plain','ABCDEFGHIJKLMNOPQRSTUVWXYZ',5,0),('wide-left','ABCDEF中q\u0301JKLMNOPQRSTUVWXYZ',7,0),
            ('wide-cut-right','ABCDEFGHIJKLMNOPQRS中VWXYZ',5,0),('bidi','ABCDEFGHLאבג\u05b0RSTUVWXYZ',10,0)]
    suffix=CSI+'?6l'+CSI+'?69l'+CSI+'31#y'+''.join(f'{CSI}{x};1;9;{x};9;{x}*y' for x in range(1,27))
    return {shape+'-'+name: ESC+'c'+CSI+'9;1H'+text+CSI+'?69h'+CSI+'5;22s'+CSI+'5;17r'+f'{CSI}{9+dy};{col+1}H'+control+suffix
            for shape,text,col,dy in shapes for name,control in [('original',''),('ich',CSI+'2@'),('dch',CSI+'2P'),
                ('decic',CSI+"2'}"),('decdc',CSI+"2'~"),('sl',CSI+'2 @'),('sr',CSI+'2 A')]}

def cells(raw):
    hits=re.findall(rb'\x1bP(\d+)!~([0-9A-Fa-f]{4})\x1b\\',raw)
    assert [int(i) for i,_ in hits]==list(range(1,27)) and b''.join(b'\x1bP'+i+b'!~'+v+b'\x1b\\' for i,v in hits)==raw,raw
    return [int(v,16) for _,v in hits]

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--xterm',default='/tmp/nemoterm-xterm-reference/xterm');parser.add_argument('--output',required=True);args=parser.parse_args()
    from xterm_state_oracle import run_cases
    path=Path(args.output); inputs=scenes();run_cases(args.xterm,str(path),inputs,['-ti','vt520','-xrm','*allowWindowOps: true'],raw_replies=True)
    j=json.loads(path.read_bytes());assert set(j['cases'])==set(inputs)
    for n,r in j['cases'].items():r['cells']=cells(bytes.fromhex(r['reply_hex']))
    assert j['cases']['plain-original']['cells']==list(b'ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    path.write_text(json.dumps(j,indent=2,ensure_ascii=True),encoding='utf8')
