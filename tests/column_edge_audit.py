"""Record both sides of a vacated DCH/DECDC/SL margin, including wide neighbours."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from column_press_cells import CSI, ESC, cells


def scenes():
    # Column 22 is the inclusive right margin. Vary the old continuation's
    # position against the gap and put either kind of glyph at the last source.
    queries = CSI+'?69l'+CSI+'31#y'+''.join(f'{CSI}{x};1;9;{x};9;{x}*y' for x in range(1,27))
    cases = {}
    for n in (1,2,3,4):
        for offset in (-1,0,1):
            tail = 22-n+offset  # zero-based; gap starts at 22-n
            for next_wide in (False,True):
                starts={tail-1:'中'}
                if next_wide:
                    if tail>=20: continue  # a second complete glyph cannot fit
                    starts[20]='界'
                line=[];i=0
                while i<26:
                    if i in starts: line.append(starts[i]);i+=2
                    else: line.append(chr(65+i));i+=1
                stem=f'n{n}-tail{offset:+d}-last'+('wide' if next_wide else 'original')
                initial=ESC+'c'+CSI+'9;1H'+''.join(line)+CSI+'?69h'+CSI+'5;22s'+CSI+'5;17r'+CSI+'9;6H'
                for name,op in [('before',''),('dch',CSI+f'{n}P'),('decdc',CSI+f"{n}'~"),('sl',CSI+f'{n} @')]:
                    cases[stem+'-'+name]=initial+op+queries
    return cases


def main():
    p=argparse.ArgumentParser();p.add_argument('--xterm');p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise RuntimeError('Hosted runner required')
    inputs=scenes()
    if args.xterm:
        from xterm_state_oracle import run_cases
        run_cases(args.xterm,str(args.output),inputs,['-ti','vt520','-xrm','*allowWindowOps: true'],raw_replies=True)
        j=json.loads(args.output.read_bytes()); raw={k:bytes.fromhex(v['reply_hex']) for k,v in j['cases'].items()}
    else:
        from protocol_oracle_window import run
        run('column-edge',[],extra_cases=[(n,s,None) for n,s in inputs.items()],barrier=(CSI+'5n',b'\x1b[0n'),
            profile=dict(NemoAllowChecksum=1,UTF8linedraw=1,WarnOnClose=0),font=os.environ['NEMOTERM_TEST_FONT'])
        source=Path(__file__).resolve().parents[1]/'research/column-edge-observed.json'
        j=json.loads(source.read_bytes()); wire={k:bytes.fromhex(v) for k,v in j['cases'].items()}
        assert all(v.endswith(b'\x1b[0n') for v in wire.values());raw={k:v[:-4] for k,v in wire.items()}
    assert set(raw)==set(inputs)
    j['observations']={k:dict(input_sha256=hashlib.sha256(s.encode()).hexdigest(),cells=cells(raw[k])) for k,s in inputs.items()}
    args.output.write_text(json.dumps(j,indent=2),encoding='utf8')


if __name__=='__main__':main()
