"""Observe upstream XTWINOPS 9 under an actual EWMH window manager in private Xvfb."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys
import time
import tty


def output(*argv):
    return subprocess.check_output(argv,text=True,timeout=3,env=dict(os.environ,LC_ALL='C'))


def geometry(window):
    info=output('xwininfo','-id',window)
    def number(label):return int(re.search(r'^\s*'+label+r':\s*(-?\d+)\s*$',info,re.M)[1])
    x,y=number('Absolute upper-left X'),number('Absolute upper-left Y')
    width,height=number('Width'),number('Height')
    props=output('xprop','-id',window,'_NET_WM_STATE','_NET_FRAME_EXTENTS')
    ext=re.search(r'_NET_FRAME_EXTENTS\(CARDINAL\) = (\d+), (\d+), (\d+), (\d+)',props)
    if not ext: return None
    l,r,t,b=map(int,ext.groups())
    return dict(client=[x,y,width,height],outer=[x-l,y-t,x+width+r,y+height+b],extents=[l,r,t,b],
                state=sorted(set(re.findall(r'_NET_WM_STATE_[A-Z_]+',props))))


def stable(window):
    until=time.monotonic()+3; previous=None; since=0
    while time.monotonic()<until:
        state=geometry(window);now=time.monotonic()
        if state!=previous:previous=state;since=now
        elif state and now-since>=.30:return state
        time.sleep(.035)
    raise RuntimeError(('window did not settle',previous))


def capture_child(args):
    tty.setraw(0);window=os.environ['WINDOWID'];row=dict(window=window,steps=[])
    try:
        row['initial']=stable(window)
        for op in args.ops.split(','):
            seq=f'\x1b[{op}t\x1b[5n'.encode();os.write(1,seq);reply=b'';until=time.monotonic()+3
            while not reply.endswith(b'\x1b[0n') and time.monotonic()<until:
                if select.select([0],[],[],.1)[0]:reply+=os.read(0,256)
            step=dict(op=op,sequence=seq.hex(),reply=reply.hex());row['steps'].append(step)
            if reply!=b'\x1b[0n':raise RuntimeError(('DSR',reply.hex()))
            step.update(stable(window))
        row['completed']=True
    finally:args.output.write_text(json.dumps(row,indent=2)+'\n')


def collect(args):
    args.output.parent.mkdir(parents=True,exist_ok=True)
    record=dict(reference_sha256=hashlib.sha256(Path(args.xterm).read_bytes()).hexdigest(),
                xterm_version=output(args.xterm,'-version').strip(),wm_version=output('openbox','--version').strip(),cases={})
    with (args.output.parent/'openbox.log').open('w') as log, subprocess.Popen(['openbox','--sm-disable'],stdout=log,stderr=log) as wm:
        try:
            until=time.monotonic()+5
            while not re.search(r'window id # 0x[1-9a-fA-F]',output('xprop','-root','_NET_SUPPORTING_WM_CHECK')):
                if wm.poll() is not None or time.monotonic()>until:raise RuntimeError('Openbox did not initialize')
                time.sleep(.05)
            record['root']=output('xprop','-root','_NET_WORKAREA','_NET_SUPPORTING_WM_CHECK').splitlines()
            streams={'vertical':'9;2,9;0','horizontal':'9;3,9;0','switch-axes':'9;2,9;3,9;0',
                     'both-to-one':'9;1,9;2,9','one-to-both':'9;3,9;1,9;0'}
            for name,ops in streams.items():
                path=args.output.parent/(name+'.json');cmd=[args.xterm,'-geometry','64x16+93+71','-fa','monospace',
                    '-xrm','*allowWindowOps: true','-xrm','*disallowedWindowOps:',
                    '-e',sys.executable,str(Path(__file__).resolve()),'--child','--ops',ops,'--output',str(path.resolve())]
                p=subprocess.run(cmd,timeout=20,stdout=log,stderr=log)
                row=record['cases'][name]=json.loads(path.read_text()); assert p.returncode==0 and row.get('completed'),(name,row)
                first=row['initial']['outer'];row['changed_edges']=[[i for i,(a,b) in enumerate(zip(first,s['outer'])) if a!=b] for s in row['steps']]
            # Test just the standalone directional requests as reference gates.
            # Preserve the actual WM's choices for the longer compositions.
            for name,indices in [('vertical',[1,3]),('horizontal',[0,2])]:
                row=record['cases'][name];assert row['changed_edges'][0]==indices,(name,row)
            record['completed']=True
        finally:
            args.output.write_text(json.dumps(record,indent=2)+'\n');wm.terminate()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--xterm');parser.add_argument('--child',action='store_true');parser.add_argument('--ops');parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    (capture_child if args.child else collect)(args)
