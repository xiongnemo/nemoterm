"""Original XTerm measurements for DEC line/page requests, separate from Windows selection."""
import argparse
import json
import os
from pathlib import Path
import re

from xterm_state_oracle import run_cases


CSI = '\x1b['
QUERY = CSI+'18t'+CSI+'6n'+''.join(CSI+f'{x};1;4;{x};4;{x}*y' for x in range(3,7))


def collect(executable, directory):
    directory.mkdir(parents=True, exist_ok=False)
    families = {'lines': ('t', [24, 28, 24, 32, 24]),
                'rows': ('*|', [24, 28, 24, 18, 24, 0]),
                'columns': ('$|', [80, 86, 80, 72, 132, 80, 0])}
    summary = {}
    for policy, deny in [('allowed',''), ('deny-xtwinops-characters','SetWinSizeChars')]:
        for name, (suffix, params) in families.items():
            trace = {'paint':CSI+'?25l'+CSI+'4;3HA中Z'+CSI+'1;1H'+CSI+'31#y'+QUERY}
            for i, arg in enumerate(params):
                trace[f'{i}-request-{arg}'] = CSI+str(arg)+suffix+QUERY
                trace[f'{i}-readback'] = QUERY
            output = directory/f'{name}-{policy}.json'
            run_cases(executable,output,trace,['-ti','vt520','-xrm','*allowWindowOps: true',
                      '-xrm','*disallowedWindowOps: '+deny],raw_replies=True)
            steps = json.loads(output.read_text())['cases']; brief = summary[name+'-'+policy] = {}
            for stage in trace:
                reply=bytes.fromhex(steps[stage]['reply_hex'])
                grid=re.match(rb'\x1b\[8;(\d+);(\d+)t',reply)
                assert grid and reply.count(b'!~')==4,(name,policy,stage,reply)
                brief[stage]={'columns':int(grid[2]),'rows':int(grid[1]),'reply_hex':reply.hex()}
    (directory/'grid-summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    if os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise RuntimeError('Requires a hosted runner')
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--xterm',required=True);ap.add_argument('--directory',type=Path,required=True)
    args=ap.parse_args();collect(args.xterm,args.directory)
