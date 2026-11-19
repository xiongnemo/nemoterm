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

def product():
    import hashlib
    import os
    from protocol_oracle_window import run
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    root=Path(__file__).resolve().parents[1]; path=root/'research/column-press-observed.json'
    ref=json.loads((root/'tests/fixtures/column-press-xterm.json').read_bytes()); inputs=scenes()
    assert set(inputs)==set(ref['cases'])
    for n,s in inputs.items():assert hashlib.sha256(s.encode()).hexdigest()==ref['cases'][n]['input_sha256'],n
    marker=b'\x1b[0n'
    run('column-press',[],extra_cases=[(n,s,None) for n,s in inputs.items()],barrier=(CSI+'5n',marker),
        profile=dict(NemoAllowChecksum=1,UTF8linedraw=1,WarnOnClose=0),font=os.environ['NEMOTERM_TEST_FONT'])
    j=json.loads(path.read_bytes());j['reference_sha256']=ref['sha256'];j['differences']={}
    for n,r in ref['cases'].items():
        raw=bytes.fromhex(j['cases'][n]);assert raw.endswith(marker),n
        expected=cells(bytes.fromhex(r['reply_hex']));actual=cells(raw[:-len(marker)])
        j['differences'][n]=[[i,a,b] for i,(a,b) in enumerate(zip(expected,actual)) if a!=b]
    mismatches={n:v for n,v in j['differences'].items() if v};j['matched']=len(inputs)-len(mismatches)
    path.write_text(json.dumps(j,indent=2),encoding='utf8');assert not mismatches,mismatches


if __name__=='__main__':
    import sys
    if sys.argv[1:]==['--product']:
        product();sys.exit(0)
    parser=argparse.ArgumentParser();parser.add_argument('--xterm',default='/tmp/nemoterm-xterm-reference/xterm');parser.add_argument('--output',required=True);args=parser.parse_args()
    from xterm_state_oracle import run_cases
    path=Path(args.output); inputs=scenes();run_cases(args.xterm,str(path),inputs,['-ti','vt520','-xrm','*allowWindowOps: true'],raw_replies=True)
    j=json.loads(path.read_bytes());assert set(j['cases'])==set(inputs)
    for n,r in j['cases'].items():r['cells']=cells(bytes.fromhex(r['reply_hex']))
    assert j['cases']['plain-original']['cells']==list(b'ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    path.write_text(json.dumps(j,indent=2,ensure_ascii=True),encoding='utf8')
