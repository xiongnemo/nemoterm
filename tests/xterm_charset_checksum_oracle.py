"""Compare stored Unicode and legacy DEC checksums on a private XTerm display."""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import re
from xterm_charsets_oracle import SETS_94, SETS_96
from xterm_state_oracle import run_cases

ESC=b'\x1b'; CSI=ESC+b'['

def cases():
    result={}
    choices=[(5,94,name) for name in SETS_94]+[(5,96,name) for name in SETS_96]
    choices += [(3,94,'I'),(3,94,'J'),(2,94,'<')]
    for level,size,name in choices:
        for national in (False,True):
            for right in (False,True):
                label=f'l{level}-{size}-{name.encode().hex()}-nrc{int(national)}-'+('gr' if right else 'gl')
                # Establish identical byte-mode power-on banks regardless of
                # the emulator's configured startup encoding or DOCS cache.
                setup=CSI+b'?42l'+ESC+b'%G'+ESC+b'c'+ESC+b'%@'+ESC+b'c'
                setup+=CSI+f'{60+level};1"p'.encode()
                setup+=CSI+b'?42'+(b'h' if national else b'l')
                setup+=ESC+(b')' if size==94 else b'-')+name.encode()+(ESC+b'~' if right else b'\x0e')
                stream=setup
                for i in range(96):
                    stream+=CSI+f'{i//48+1};{i%48+1}H'.encode()+bytes([0x20+i+(0x80 if right else 0)])
                # Rectangle checksums require level 4+. Switching level keeps
                # the cells but can affect UPSS resolution: record that fact.
                stream+=CSI+b'65;1"p'
                for mode in (15,31):
                    stream+=CSI+f'{mode}#y'.encode()
                    for i in range(96):
                        row,col=i//48+1,i%48+1
                        stream+=CSI+f'{i+1};1;{row};{col};{row};{col}*y'.encode()
                stream+=CSI+b'?42l'+ESC+b'%G'
                result[label]=dict(sequence=stream,setup=setup,right=right)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--xterm',default='/tmp/nemoterm-xterm-reference/xterm')
    a=p.parse_args(); folder=a.output.with_suffix('');folder.mkdir(exist_ok=False)
    merged={}
    items=list(cases().items())
    # Legacy sums retain per-cell source charset metadata. Isolate every case
    # so a preceding case's cell metadata cannot influence this reference.
    for batch in range(len(items)):
        selected=dict(items[batch:batch+1]); path=folder/f'{batch:03}.json'
        with path.with_suffix('.log').open('w') as log, redirect_stdout(log):
            run_cases(a.xterm,path,{k:v['sequence'] for k,v in selected.items()},
                ['-ti','vt525','-xrm','*allowWindowOps: true','-xrm','*locale: false','-xrm','*wideChars: true'],
                raw_replies=True,utf8_command_line=False)
        data=json.loads(path.read_text())
        if not merged:merged={**data,'cases':{}}
        assert merged['executable_sha256']==data['executable_sha256']
        for name,record in data['cases'].items():
            checks=re.findall(rb'\x1bP([0-9]+)!~([0-9A-Fa-f]{4})\x1b\\',bytes.fromhex(record['reply_hex']))
            assert [int(n) for n,v in checks]==list(range(1,97))*2,(name,len(checks))
            record.update(setup_hex=selected[name]['setup'].hex(),right=selected[name]['right'],
                legacy=[int(v,16) for n,v in checks[:96]],unicode=[int(v,16) for n,v in checks[96:]])
        merged['cases'].update(data['cases']);a.output.write_text(json.dumps(merged,indent=2)+'\n')
        if (batch+1)%32==0 or batch+1==len(items):
            print(len(merged['cases']),'independent charset checksum streams',flush=True)
