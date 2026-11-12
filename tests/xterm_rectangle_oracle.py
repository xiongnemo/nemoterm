"""Independent XTerm rectangle editing oracle; runs on an owned Xvfb display."""
import argparse,json,re
from pathlib import Path
from xterm_state_oracle import run_cases
p=argparse.ArgumentParser();p.add_argument('--output',default='research/rectangle-xterm.json');p.add_argument('--xterm',default='/tmp/nemoterm-xterm-reference/xterm');a=p.parse_args()
b='\x1bc\x1b[?25l'
grid=''.join(f'\x1b[{i+1};1H'+chr(65+i)*12 for i in range(5))
q='\x1bP$q*x\x1b\\'
cases={
 'extent-state':b+q+'\x1b[2*x'+q+'\x1b[!p'+q+'\x1b[2*x\x1b[?1049h'+q+'\x1b[?1049l'+q+'\x1b[99*x'+q+'\x1bc'+q,
 'fill':b+grid+'\x1b[90;2;3;4;6$x',
 'fill-default':b+'ABC\x1b[$x',
 'fill-zero':b+'ABC\x1b[0;1;1;1;3$x',
 'fill-style':b+'\x1b[31;44;1;4mABC\x1b[32;45;3m\x1b[90;1;1;1;3$x',
 'fill-default-colour':b+'\x1b[31;44;1;4mABC\x1b[0m\x1b[90;1;1;1;3$x',
 'fill-protection':b+'\x1b[1"qA\x1b[0"qB\x1b[90;1;1;1;2$x\x1b[?2K',
 'fill-current-protection':b+'AB\x1b[1"q\x1b[90;1;1;1;2$x\x1b[?2K',
 'fill-charset':b+'\x1b(0\x1b[113;1;1;1;3$x',
 'fill-unicode':b+'\x1b[8364;1;1;1;3$x\x1b[20013;2;1;2;3$x',
 'fill-invalid':b+'ABC\x1b[31;1;1;1;3$x\x1b[127;1;1;1;3$x\x1b[55296;1;1;1;3$x',
 'fill-half-wide':b+'中文Z\x1b[88;1;2;1;3$x',
 'fill-origin':b+grid+'\x1b[3;5r\x1b[?6h\x1b[90;1;2;2;4$x',
 'copy':b+grid+'\x1b[1;2;2;5;1;3;4;1$v',
 'copy-overlap-down':b+grid+'\x1b[1;2;4;5;1;2;3;1$v',
 'copy-overlap-up':b+grid+'\x1b[2;3;5;6;1;1;2;1$v',
 'copy-overlap-right':b+'ABCDEFGHIJKL\x1b[1;1;1;8;1;1;3;1$v',
 'copy-pages':b+'ABC\x1b[1;1;1;3;3;2;1;7$v',
 'copy-combining-wide':b+'Á中文Z\x1b[1;1;1;6;1;2;2;1$v',
 'copy-half-wide':b+'中文Z\x1b[1;2;1;3;1;2;2;1$v',
 'copy-style-protection':b+'\x1b[31;44;1;4m\x1b[1"qA\x1b[0"qB\x1b[0m\x1b[1;1;1;2;1;2;1;1$v\x1b[2;1H\x1b[?2K',
 'copy-origin':b+grid+'\x1b[3;5r\x1b[?6h\x1b[1;1;1;3;1;2;3;1$v',
 'attrs-stream':b+grid+'\x1b[1;3;3;5;1$r',
 'attrs-rectangle':b+grid+'\x1b[2*x\x1b[1;3;3;5;1$r',
 'attrs-undrawn':b+'A B\x1b[1;1;1;6;7$r',
 'attrs-erased':b+'ABCDE\x1b[1;2H\x1b[2X\x1b[1;1;1;6;7$r',
 'attrs-rect-undrawn':b+'A B\x1b[2*x\x1b[1;1;1;6;7$r',
 'attrs-default':b+'\x1b[1;2;3;4;5;7;8;9;31;44mABC\x1b[1;1;1;3$r',
 'attrs-reset':b+'\x1b[1;2;3;4;5;7;8;9;31;44mABC\x1b[1;1;1;3;0$r',
 'attrs-ignored':b+'ABC\x1b[1;1;1;3;2;3;9;31;44$r',
 'attrs-wide-half':b+'中文\x1b[2*x\x1b[1;2;1;3;1$r',
 'attrs-reverse':b+'ABC\x1b[1;1;1;3;0$t',
 'attrs-reverse-twice':b+'ABC\x1b[1;1;1;3;4;4$t',
 'attrs-conceal':b+'ABC\x1b[1;1;1;3;8$r\x1b[1;2;1;2;8$t',
 'attrs-origin':b+grid+'\x1b[3;5r\x1b[?6h\x1b[1;2;2;4;7$r',
 'attrs-inverted-stream':b+grid+'\x1b[1;8;3;2;7$r',
 'pending-wrap':b+'\x1b[1;80HX\x1b[90;2;2;2;4$x\x1b[1;1;1;3;1;3;1;1$v\x1b[1;1;1;3;1$rY\x1b[6n',
}
for name,sequence in {
 'undrawn-ech':'\x1b[1;4H\x1b[2X',
 'undrawn-el':'\x1b[1;4H\x1b[K',
 'undrawn-colored-el':'\x1b[41m\x1b[1;4H\x1b[K',
 'undrawn-colored-ed':'\x1b[41m\x1b[2J',
 'undrawn-decsel':'ABC\x1b[?2K',
 'undrawn-decsed':'ABC\x1b[?2J',
 'undrawn-ed':'\x1b[2J',
 'undrawn-insert':'ABCD\x1b[1;2H\x1b[2@',
 'undrawn-delete':'ABCD\x1b[1;2H\x1b[2P',
 'undrawn-decera':'\x1b[1;2;1;4$z',
 'undrawn-decsera':'\x1b[1;2;1;4${',
 'undrawn-copy':'\x1b[1;1;1;3;1;2;1;1$v',
 'attrs-no-param-blank':'\x1b[2*x\x1b[1;1;1;3$r',
}.items(): cases[name]=b+sequence+'\x1b[0*x\x1b[1;1;2;8;7$r'
cells=[(r,c) for r in range(1,6) for c in range(1,13)]
suffix='\x1b[6n'+q+'\x1b[?6l\x1b[31#y'
for i,(r,c) in enumerate(cells,1):suffix+=f'\x1b[{i};1;{r};{c};{r};{c}*y\x1b[{r};{c};{r};{c}#|'
run_cases(a.xterm,a.output,{k:v+suffix for k,v in cases.items()},['-ti','vt420','-xrm','*allowWindowOps: true'])
p=Path(a.output);data=json.loads(p.read_text())
for name,case in data['cases'].items():
    found=re.findall(r'\x1bP(\d+)!~([0-9a-fA-F]+)\x1b\\\x1b\[([^m]*)m',case['reply'])
    assert len(found)==len(cells),(name,len(found))
    case['cells']=[dict(row=r,column=c,checksum=int(value,16),sgr=sgr) for (r,c),(_,value,sgr) in zip(cells,found)]
p.write_text(json.dumps(data,indent=2))
