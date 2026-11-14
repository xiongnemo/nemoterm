"""Independently observe charset checksum lifetimes across terminal edits."""
import argparse,json
from contextlib import redirect_stdout
from pathlib import Path
from xterm_state_oracle import run_cases
E=b'\x1b';C=E+b'[';S=E+b'\\'
RESET=C+b'?42l'+E+b'%G'+E+b'c'+C+b'65;1"p'+E+b'%G'
GERMAN=RESET+C+b'?42h'+E+b'(K'+b'[\\]'
def sums(row=1,cols=3):
    result=b''
    for mode in (15,31):
        result+=C+str(mode).encode()+b'#y'
        for col in range(1,cols+1):result+=C+f'{mode*100+col};1;{row};{col};{row};{col}*y'.encode()
    return result
def cases():
    neutral=E+b'(B'+C+b'?42l'
    return {
        'redesignate':GERMAN+sums()+neutral+sums(),
        'repeat':GERMAN+neutral+C+b'1;1H'+C+b'3b'+sums(),
        'overwrite':GERMAN+neutral+C+b'1;2H'+b'Q'+sums(),
        'copy':GERMAN+neutral+C+b'1;1;1;3;1;2;1;1$v'+sums(2),
        'copy-overlap':GERMAN+neutral+C+b'1;1;1;2;1;1;2;1$v'+sums(),
        'attribute':GERMAN+C+b'2*x'+C+b'1;1;1;3;1;4;53$r'+sums(),
        'erase':GERMAN+C+b'1;2;1;2$z'+sums(),
        'insert':GERMAN+C+b'1;2H'+C+b'@'+sums(cols=4),
        'delete':GERMAN+C+b'1;2H'+C+b'P'+sums(cols=4),
        'fill':GERMAN+C+b'91;2;1;2;3$x'+sums(2),
        'soft-reset':GERMAN+C+b'!p'+sums(),
        'alternate':GERMAN+C+b'?1049h'+RESET+b'XYZ'+C+b'?1049l'+sums(),
        'scroll':GERMAN+C+b'1T'+sums(2),
        'upss-reassign':RESET+E+b'%@'+E+b'(<'+E+b'P1!uF'+S+b'ABC'+E+b'P1!uA'+S+sums(),
        'byte-pound-to-utf8':RESET+E+b'%@'+C+b'?42h'+E+b'(A'+b'#'+C+b'?42l'+E+b'%G'+sums(cols=1),
        'byte-nrc-overwrite':RESET+E+b'%@'+C+b'?42h'+E+b'(A'+b'#'+C+b'?42l'+E+b'%G'+C+b'H'+b'#'+sums(cols=1),
    }
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();folder=a.output.with_suffix('');folder.mkdir(exist_ok=False);merged={}
    for name,sequence in cases().items():
        path=folder/(name+'.json')
        with path.with_suffix('.log').open('w') as log,redirect_stdout(log):
            run_cases('/tmp/nemoterm-xterm-reference/xterm',path,{name:sequence},
                ['-ti','vt525','-xrm','*allowWindowOps: true','-xrm','*locale: false','-xrm','*wideChars: true'],
                raw_replies=True,utf8_command_line=False)
        row=json.loads(path.read_text())
        if not merged:merged={**row,'cases':{}}
        assert merged['executable_sha256']==row['executable_sha256']
        merged['cases'].update(row['cases']);a.output.write_text(json.dumps(merged,indent=2)+'\n')
    print(len(merged['cases']),'independent lifecycle streams')
