"""Record the actual bytes emitted by the hosted ncurses linux terminfo entry."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
out=Path('build/linux-palette-reference');out.mkdir(parents=True,exist_ok=False)
env=dict(os.environ,TERM='linux',LC_ALL='C'); report={'terminal':'linux','entries':[]};rc=1
try:
    tput=Path(shutil.which('tput')).resolve(strict=True)
    report.update(tput_sha256=hashlib.sha256(tput.read_bytes()).hexdigest(),ncurses=subprocess.check_output([tput,'-V'],env=env,text=True).strip())
    (out/'linux.terminfo').write_bytes(subprocess.check_output(['infocmp','-x','-1','linux'],env=env))
    for i in range(16):
        requested=[200*(i%4),200*(i//4),200*(1+i%5)]
        wire=subprocess.check_output([tput,'-T','linux','initc',str(i),*map(str,requested)],env=env)
        row=dict(index=i,requested=requested,hex=wire.hex());report['entries'].append(row)
        assert re.fullmatch(rb'\x1b\]P[0-9a-fA-F]{7}',wire) and int(wire[3:4],16)==i, row
        row['rgb']=list(bytes.fromhex(wire[4:].decode()));assert all(abs(c-v*255/1000)<=1 for c,v in zip(row['rgb'],requested)),row
    reset=subprocess.check_output([tput,'-T','linux','oc'],env=env);report['reset']=reset.hex();assert reset==b'\x1b]R',reset
    assert len({tuple(row['rgb']) for row in report['entries']})==16
    rc=0
finally:
    report['passed']=rc==0;(out/'linux-palette.json').write_text(json.dumps(report,indent=2))
