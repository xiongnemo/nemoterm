"""Read independent XTerm cells via its checksums and rectangle SGR query."""
import argparse
import json
from pathlib import Path
import re
from xterm_state_oracle import run_cases

parser=argparse.ArgumentParser()
parser.add_argument('--xterm',default='/tmp/nemoterm-xterm-reference/xterm')
parser.add_argument('--output',default='research/selective-erase-xterm.json')
args=parser.parse_args()
q='\x1bP$q"q\x1b\\'
base='\x1bc\x1b[?25l'
sample='A\x1b[1"qB\x1b[0"qC'
cases={
    'basic-selective-line':base+sample+'\x1b[?2K',
    'normal-line-ignores-protection':base+sample+'\x1b[2K',
    'sgr-independent':base+'\x1b[1"qA\x1b[0mB\x1b[?2K',
    'protection-query':base+q+'\x1b[1"q'+q+'\x1b[2"q'+q+'\x1b[1;2"q'+q+
        '\x1b[999"q'+q+'\x1b[0:0"q'+q,
    'cursor-protection':base+'\x1b[1"q\x1b7\x1b[0"q'+q+'\x1b8'+q,
    'soft-old-protected-cells':base+sample+'\x1b[!p'+q+'\x1b[?2K',
    'selective-rendition':base+'\x1b[31;44;1;4mABC\x1b[32;45m\x1b[?2K',
    'selective-rect-rendition':base+'\x1b[31;44;1;4mA\x1b[1"qB\x1b[0"qC'
        '\x1b[32;45m\x1b[1;1;1;3${',
    'normal-rect-rendition':base+'\x1b[31;44;1;4mABC\x1b[32;45;3m\x1b[1;1;1;3$z',
    'normal-rect-default-rendition':base+'\x1b[31;44;1;4mABC\x1b[0m\x1b[1;1;1;3$z',
    'selective-wide-left':base+'\x1b[1"q中\x1b[0"q文XYZ\x1b[1;2H\x1b[?0K',
    'selective-wide-right':base+'中\x1b[1"q文\x1b[0"qXYZ\x1b[1;3H\x1b[?1K',
    'rect-wide-boundary':base+'中\x1b[1"q文\x1b[0"qXYZ\x1b[1;2;1;3${',
    'pending-wrap-selective':base+'\x1b[1;80HX\x1b[?KZ\x1b[6n',
    'pending-wrap-protected':base+'\x1b[1"q\x1b[1;80HX\x1b[?2KZ\x1b[6n',
    'pending-wrap-rectangle':base+'\x1b[1;80HX\x1b[1;1;1;3${Z\x1b[6n',
    'origin-rectangle':base+'111111\x1b[2;1H222222\x1b[3;1H333333\x1b[4;1H444444'
        '\x1b[5;1H555555\x1b[3;5r\x1b[?6h\x1b[1;2;2;4${',
    'origin-default-rectangle':base+'111111\x1b[2;1H222222\x1b[3;1H333333\x1b[4;1H444444'
        '\x1b[5;1H555555\x1b[3;5r\x1b[?6h\x1b[${',
    'inverted-rectangle':base+'ABCDEF\x1b[1;5;1;2${',
    'outside-rectangle':base+'ABCDEF\x1b[1;80HZ\x1b[1;999;1;999${',
    'selective-invalid':base+sample+'\x1b[?4K\x1b[?999J',
    'selective-extra-parameter':base+sample+'\x1b[?2;9K',
}
# Checksum flags: positive, no attributes, no trimming, include undrawn,
# report full Unicode. Query each cell independently, including its SGR.
cells=[(r,c) for r in range(1,6) for c in range(1,9)]+[(1,79),(1,80),(2,79),(2,80)]
suffix='\x1b[6n'+q+'\x1b[?6l\x1b[31#y'
for index,(row,col) in enumerate(cells,1):
    suffix+=f'\x1b[{index};1;{row};{col};{row};{col}*y\x1b[{row};{col};{row};{col}#|'
run_cases(args.xterm,args.output,{k:v+suffix for k,v in cases.items()},
    ['-ti','vt420','-xrm','*allowWindowOps: true'])
path=Path(args.output)
data=json.loads(path.read_text())
for name,case in data['cases'].items():
    raw=case['reply']
    found=re.findall(r'\x1bP(\d+)!~([0-9A-Fa-f]+)\x1b\\\x1b\[([^m]*)m',raw)
    assert len(found)==len(cells),(name,raw)
    case['cells']=[dict(row=row,column=col,codepoint=int(value,16),sgr=sgr)
        for (row,col),(index,value,sgr) in zip(cells,found)]
    print(name,[(r,''.join(chr(c['codepoint']) if c['codepoint'] else '_' for c in case['cells']
        if c['row']==r and c['column']<=8)) for r in range(1,6)],flush=True)
path.write_text(json.dumps(data,indent=2))
