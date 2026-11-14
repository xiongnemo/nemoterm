"""Exact ISO 2022 byte streams on a private reference XTerm/Xvfb display."""
import argparse,json,re
from pathlib import Path
from xterm_state_oracle import run_cases

ESC=b'\x1b';CSI=ESC+b'['
SETS_94=['B','A','0','4','5','C','R','f','Q','9','K','Y','E','6','`','Z','7','H','=',
         '%6','">','%=','%2','&5','%3','%5','>','"?','"4','%0','&4','I','J','<']
SETS_96=['A','B','F','H','L','M']

def mapping_cases():
    cases={}
    for size,sets in [(94,SETS_94),(96,SETS_96)]:
        for designation in sets:
            for national in (False,True):
                for use_utf8 in (False,True):
                    for right in (False,True):
                        name=f'{size}-{designation.encode().hex()}-nrc{int(national)}-utf{int(use_utf8)}-'+('gr' if right else 'gl')
                        # Disable NRC before resetting to restore its temporary
                        # UTF-8 parser swap. Then choose the base encoding and
                        # enable NRC, so Unicode NRCS mappings are observable.
                        start=CSI+b'?42l'+ESC+b'c'+CSI+b'65;1"p'
                        start+=ESC+(b'%G' if use_utf8 else b'%@')
                        start+=CSI+b'?42'+(b'h' if national else b'l')
                        introducer=b')' if size==94 else b'-'
                        start+=ESC+introducer+designation.encode()+ (ESC+b'~' if right else b'\x0e')
                        sequence=start
                        for i,value in enumerate(range(0x20,0x80)):
                            row,col=1+i//48,1+i%48
                            sequence+=CSI+f'{row};{col}H'.encode()+bytes([value|0x80 if right else value])
                        # Bit 4 asks for stored Unicode cell values; retain the
                        # designated sets until after the presentation report.
                        sequence+=CSI+b'31#y'
                        for i in range(96):
                            row,col=1+i//48,1+i%48
                            sequence+=CSI+f'{i+1};1;{row};{col};{row};{col}*y'.encode()
                        sequence+=CSI+b'1$w'+CSI+b'?42$p'+CSI+b'?42l'+ESC+b'%G'
                        cases[name]=sequence
    return cases

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm',default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output',default='research/charsets-xterm.json')
    parser.add_argument('--batch',type=int,default=0)
    args=parser.parse_args()
    all_cases=mapping_cases();items=list(all_cases.items())
    # The shared child has a finite lifetime; bound each collector invocation.
    selected=dict(items[args.batch*80:(args.batch+1)*80])
    assert selected
    run_cases(args.xterm,args.output,selected,['-ti','vt525','-xrm','*allowWindowOps: true',
        '-xrm','*locale: false','-xrm','*wideChars: true'],raw_replies=True,utf8_command_line=False)
    path=Path(args.output);data=json.loads(path.read_text())
    for name,case in data['cases'].items():
        raw=bytes.fromhex(case['reply_hex'])
        cells=re.findall(rb'\x1bP([0-9]+)!~([0-9A-Fa-f]{4})\x1b\\',raw)
        assert len(cells)==96,(name,len(cells))
        assert [int(n) for n,v in cells]==list(range(1,97)),name
        case['cells']=[int(v,16) for n,v in cells]
    path.write_text(json.dumps(data,indent=2)+'\n')
