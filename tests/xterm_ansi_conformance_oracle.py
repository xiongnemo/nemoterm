"""Observe ANSI conformance shifts in fresh pinned XTerm/Xvfb processes.

This collector authors input streams, not expected implementation results.
Unicode cell checksums preserve the rendered characters across the temporary
DECSCL level increase needed to query cells from lower DEC operating levels.
"""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import re
from xterm_state_oracle import run_cases

E=b'\x1b'; C=E+b'['
RESET=C+b'?42l'+E+b'%G'+E+b'c'+E+b'%@'+E+b'c'+C+b'65;1"p'
BANKS=C+b'?42h'+E+b'(B'+E+b')0'+E+b'*5'+E+b'+R'+b'\x0f'
PROBE=b'q@[\\]^'
REPORT=C+b'1$w'
SHIFTS={'ls2':E+b'n','ls3':E+b'o','ls1r':E+b'~','ls2r':E+b'}',
        'ls3r':E+b'|','so':b'\x0e','si':b'\x0f','ss2':E+b'N','ss3':E+b'O'}

def cases():
    result={}
    def add(name, setup, body, text=PROBE, **metadata):
        # Only Unicode sums are compared: changing the DEC operating level
        # can change the interpretation of legacy UPSS checksum metadata.
        suffix=E+b' F'+C+b'65;1"p'+C+b'31#y'
        suffix+=b''.join(C+f'{i};1;1;{i};1;{i}*y'.encode() for i in range(1,len(text)+1))
        stream=RESET+setup+C+b'2J'+C+b'H'+REPORT+body+text+REPORT+C+b'6n'+suffix
        result[name]=dict(sequence=stream,cell_count=len(text),**metadata)
    add('literal-ascii',E+b'(B',b'',b'A',control=[0x0041])
    add('literal-dec-line',E+b'(0',b'',b'q',control=[0x2500])
    add('literal-national-finnish',C+b'?42h'+E+b'(5',b'',b'[',control=[0x00c4])
    for dec in range(1,6):
        for ansi in ('default','L','M','N'):
            setup=C+f'{60+dec};1"p'.encode()+BANKS
            if ansi!='default':setup+=E+b' '+ansi.encode()
            for shift,command in SHIFTS.items():
                text=bytes(x+0x80 for x in PROBE) if shift.endswith('r') else PROBE
                add(f'dec{dec}-ansi{ansi}-{shift}',setup,command,text,
                    dec_level=dec,ansi_command=ansi,shift=shift)
    for ansi in ('L','M','N'):
        setup=BANKS+E+b' '+ansi.encode()
        transitions={
            'soft-reset':C+b'!p'+BANKS,
            'hard-reset':E+b'c'+E+b'%@'+BANKS,
            'dec-level-reset':C+b'65;1"p'+BANKS,
            'cursor-save-restore':E+b'7'+E+b' N'+E+b'8',
            'cursor-save-restores-lower':E+b' N'+E+b'7'+E+b' L'+E+b'8',
            'alternate-enter':C+b'?1049h'+BANKS,
            'alternate-return':C+b'?1049h'+E+b' N'+C+b'?1049l',
            'alternate-return-lower':C+b'?1049h'+E+b' L'+C+b'?1049l',
            'docs-round-trip':E+b'%G'+E+b'%@',
            'eight-bit-replies':E+b' G',
            'unknown-final':E+b' Q',
            'cancel-can':E+b' '+b'\x18',
            'cancel-sub':E+b' '+b'\x1a',
        }
        for name,transition in transitions.items():
            add(f'ansi{ansi}-{name}',setup,transition+E+b'n',ansi_command=ansi,transition=name)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm',default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();parts=args.output.with_suffix('');parts.mkdir(exist_ok=False)
    options=['-ti','vt525','-xrm','*allowWindowOps: true',
             '-xrm','*locale: false','-xrm','*wideChars: true']
    result={};authored=cases()
    for index,(name,case) in enumerate(authored.items()):
        path=parts/f'{index:03}.json'
        with path.with_suffix('.log').open('w') as log,redirect_stdout(log):
            run_cases(args.xterm,path,{name:case['sequence']},options,
                      raw_replies=True,utf8_command_line=False)
        captured=json.loads(path.read_text())
        if not result:result={**captured,'cases':{},'scope':'Independent Unicode cells and raw state/query replies; not product acceptance.'}
        assert result['executable_sha256']==captured['executable_sha256']
        observation=captured['cases'][name]
        sums=re.findall(rb'\x1bP([0-9]+)!~([0-9A-Fa-f]{4})\x1b\\',bytes.fromhex(observation['reply_hex']))
        assert [int(n) for n,v in sums]==list(range(1,case['cell_count']+1)),(name,len(sums))
        observation.update({k:v for k,v in case.items() if k!='sequence'})
        observation['unicode_cells']=[int(v,16) for n,v in sums]
        result['cases'][name]=observation
        args.output.write_text(json.dumps(result,indent=2)+'\n')
        if 'control' in case:assert observation['unicode_cells']==case['control'],(name,observation)
        if (index+1)%25==0 or index+1==len(authored):
            print(index+1,'independent ANSI conformance streams retained',flush=True)
    result['completed']=True;args.output.write_text(json.dumps(result,indent=2)+'\n')
