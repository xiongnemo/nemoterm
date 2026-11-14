"""ISO 2022 state transitions on a private XTerm/Xvfb display."""
import argparse
import json
from pathlib import Path
from xterm_state_oracle import run_cases

ESC=b'\x1b'; CSI=ESC+b'['
RESET=CSI+b'?42l'+ESC+b'c'+CSI+b'65;1"p'+ESC+b'%G'
REPORT=CSI+b'1$w'+CSI+b'?42$p'
CELLS=CSI+b'31#y'+b''.join(CSI+f'{n};1;1;{n};1;{n}*y'.encode() for n in range(1,7))
SETS=CSI+b'?42h'+ESC+b'(%6'+ESC+b'-F'+ESC+b'*&4'+ESC+b'/H'

def cases():
    streams={
        'four-banks': SETS+REPORT,
        'restore-four-banks': SETS+ESC+b'7'+ESC+b'(B'+ESC+b')B'+ESC+b'*B'+ESC+b'+B'+ESC+b'8'+REPORT,
        'restore-four-banks-1049': SETS+CSI+b'?1049h'+ESC+b'(B'+ESC+b')B'+ESC+b'*B'+ESC+b'+B'+CSI+b'?1049l'+REPORT,
        'restore-information': CSI+b'?42h'+ESC+b'P1$t1;1;1;@;@;@;2;3;J;%6F&4H'+ESC+b'\\'+REPORT,
        'nrc-soft-reset': SETS+CSI+b'!p'+REPORT,
        'nrc-hard-reset': SETS+ESC+b'c'+REPORT,
        'nrc-saved-mode': CSI+b'?42h'+CSI+b'?42s'+CSI+b'?42l'+CSI+b'?42r'+REPORT,
        'nrc-duplicate-mode': CSI+b'?42h'+CSI+b'?42h'+ESC+b'(K[\\]'+CELLS+REPORT,
        'nrc-restores-utf8': CSI+b'?42h'+CSI+b'?42l'+'中'.encode()+CELLS+REPORT,
        'docs-byte-override': ESC+b'%@'+'中'.encode()+CELLS+REPORT,
        'docs-utf8-override': ESC+b'%@'+ESC+b'%G'+'中'.encode()+CELLS+REPORT,
        'docs-byte-cursor-save': ESC+b'%@'+ESC+b'7'+ESC+b'%G'+ESC+b'8'+'中'.encode()+CELLS+REPORT,
        'docs-utf8-cursor-save': ESC+b'%G'+ESC+b'7'+ESC+b'%@'+ESC+b'8'+'中'.encode()+CELLS+REPORT,
        'docs-byte-alternate': ESC+b'%@'+CSI+b'?1049h'+ESC+b'%G'+CSI+b'?1049l'+'中'.encode()+CELLS+REPORT,
        'unknown-recovers-ascii': CSI+b'?42h'+ESC+b'(K'+ESC+b'(%9[\\]'+CELLS+REPORT,
        'cancel-intermediate': CSI+b'?42h'+ESC+b'(K'+ESC+b'(%\x18[\\]'+CELLS+REPORT,
        'malformed-third-intermediate': CSI+b'?42h'+ESC+b'(K'+ESC+b'(%&6[\\]'+CELLS+REPORT,
        'ss2': CSI+b'?42h'+ESC+b'*K'+ESC+b'N[[['+CELLS+REPORT,
        'ss3': CSI+b'?42h'+ESC+b'+%6'+ESC+b'O[[['+CELLS+REPORT,
        'ss2-through-controls': CSI+b'?42h'+ESC+b'*K'+ESC+b'N\x07\r[[['+CELLS+REPORT,
        'ss2-gr-then-gl': CSI+b'?42h'+ESC+b'*K'+ESC+b'N\xdb['+CELLS+REPORT,
        'ss3-save-restore': CSI+b'?42h'+ESC+b'+%6'+ESC+b'O'+ESC+b'7['+ESC+b'8['+CELLS+REPORT,
        'g2-96': ESC+b'%@'+ESC+b'.F'+ESC+b'nABC'+CELLS+REPORT,
        'g3-96': ESC+b'%@'+ESC+b'/L'+ESC+b'oABC'+CELLS+REPORT,
        'nrc-toggle-keeps-designation': CSI+b'?42h'+ESC+b'(K'+CSI+b'?42l'+ESC+b'%@'+b'['+CELLS+REPORT,
    }
    return {name:RESET+value+CSI+b'?42l'+ESC+b'%G' for name,value in streams.items()}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--xterm',default='/tmp/nemoterm-xterm-reference/xterm')
    p.add_argument('--output',required=True)
    p.add_argument('--isolated',action='store_true',help='Start a fresh reference process for each case')
    args=p.parse_args()
    options=['-ti','vt525','-xrm','*allowWindowOps: true',
             '-xrm','*locale: false','-xrm','*wideChars: true']
    if args.isolated:
        dest=Path(args.output); parts=dest.with_suffix(''); parts.mkdir(exist_ok=True)
        result={}
        for name,sequence in cases().items():
            path=parts/(name+'.json')
            run_cases(args.xterm,path,{name:sequence},options,raw_replies=True,utf8_command_line=False)
            part=json.loads(path.read_text())
            if not result:result={**part,'cases':{}}
            assert result['executable_sha256']==part['executable_sha256']
            result['cases'].update(part['cases'])
            dest.write_text(json.dumps(result,indent=2)+'\n')
    else:
        run_cases(args.xterm,args.output,cases(),options,raw_replies=True,utf8_command_line=False)
