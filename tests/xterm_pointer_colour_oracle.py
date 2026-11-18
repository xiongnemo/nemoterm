"""Observe OSC mouse colours on a pinned XTerm and its actual private X11 cursor."""
import argparse
from collections import Counter
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from xterm_locator_oracle import Display, read, write
from xterm_state_oracle import child

ESC=b'\x1b';CSI=ESC+b'[';ST=ESC+b'\\';DSR=CSI+b'5n';OK=CSI+b'0n'
def osc(command,value=None,end=ST):
    return ESC+b']'+str(command).encode()+(b'' if value is None else b';'+value)+end
Q=osc(13,b'?')+osc(14,b'?')
STEPS=[('initial',Q),('set-foreground',osc(13,b'#12a45c')+Q),
       ('set-background',osc(14,b'#d632b4')+Q),('bel-chain',osc(13,b'?;?',b'\x07')),
       ('unrelated-text-colours',osc(10,b'#193f71;#501023')+Q),('reverse',CSI+b'?5h'+Q),
       ('set-in-reverse',osc(13,b'#2288ee;#f09a38')+Q),('reverse-off',CSI+b'?5l'+Q),
       ('bad-then-valid',osc(13,b'not_a_colour;#5511dd')+Q),('reset-foreground',osc(113)+Q),
       ('reset-background-payload',osc(114,b'ignored')+Q),('named',osc(13,b'red;blue')+Q),
       ('soft-reset',CSI+b'!p'+Q),('alternate',CSI+b'?1049h'+Q),('restore-main',CSI+b'?1049l'+Q),
       ('push',CSI+b'#P'+osc(13,b'#abcdef;#123456')+Q),('pop',CSI+b'#Q'+Q),
       ('hard-reset',ESC+b'c'+Q),('reset-both',osc(113)+osc(114)+Q),
       ('fresh-pair',osc(13,b'#229933;#6611dd')+Q),('payload-reset-foreground',osc(113,b'ignored')+Q),
       ('plain-reset-both',osc(113)+osc(114)+Q),('soft-pair',osc(13,b'red;blue')+CSI+b'!p'+Q),
       ('soft-plain-resets',osc(113)+osc(114)+Q),('ris-pair',osc(13,b'red;blue')+ESC+b'c'+Q),
       ('ris-plain-resets',osc(113)+osc(114)+Q),('unchanged-push-pop',osc(13,b'green;cyan')+CSI+b'#P'+CSI+b'#Q'+Q),
       ('unchanged-pop-resets',osc(113)+osc(114)+Q),('changed-only-foreground-then-pop',osc(13,b'green;cyan')+CSI+b'#P'+osc(13,b'blue')+CSI+b'#Q'+Q),
       ('changed-pop-resets',osc(113)+osc(114)+Q),('plain-after-pop-set-one',osc(14,b'#883399')+osc(113)+osc(114)+Q)]
PROFILES={'default':(), 'explicit':('pointerColor: #2678ae','pointerColorBackground: #b2d460'),
          'deny-set':('allowColorOps: false','disallowedColorOps: SetColor'),
          'deny-get':('allowColorOps: false','disallowedColorOps: GetColor')}

class Cursor(c.Structure):
    _fields_=[('x',c.c_short),('y',c.c_short),('width',c.c_ushort),('height',c.c_ushort),
              ('xhot',c.c_ushort),('yhot',c.c_ushort),('serial',c.c_ulong),('pixels',c.POINTER(c.c_ulong))]

def run(exe,display_name,base,name,params):
    folder=base/name;folder.mkdir(); report=folder/'child.json';control=folder/'control.json'
    view=Display(display_name);fix=c.CDLL('libXfixes.so.3');fix.XFixesGetCursorImage.argtypes=[c.c_void_p];fix.XFixesGetCursorImage.restype=c.POINTER(Cursor)
    args=[str(exe),'-geometry','80x24+10+10','-b','2','-bw','0','+sb','-fn','fixed','-ti','vt520','-fg','white','-bg','black']
    for value in ('pointerMode: 0','pointerShape: xterm',*params):args+=['-xrm','XTerm*'+value]
    transcript=dict(arguments=args,steps=[],completed=False)
    with (folder/'stderr.log').open('wb') as err:
        process=subprocess.Popen(args+['-e',sys.executable,str(Path(__file__).resolve()),'--child',str(report),str(control)],env=dict(os.environ,DISPLAY=display_name),stderr=err,stdout=subprocess.DEVNULL)
        def emit(phase,wire):
            write(control,dict(phase=phase,sequence_hex=(wire+DSR).hex()));until=time.monotonic()+7
            while time.monotonic()<until:
                obj=read(report);data=bytes.fromhex(obj.get('hex',''))
                if obj.get('phase')==phase and data.endswith(OK):return data[:-len(OK)]
                assert process.poll() is None,(phase,process.returncode,obj)
                time.sleep(.01)
            raise TimeoutError((phase,read(report)))
        def cursor():
            view.x.XSync(view.d,False);image=fix.XFixesGetCursorImage(view.d);assert image
            try:
                d=image.contents;assert 0<d.width*d.height<=512*512
                raw=b''.join((p&0xffffffff).to_bytes(4,'big') for p in d.pixels[:d.width*d.height]);colours=Counter(raw[i:i+4].hex() for i in range(0,len(raw),4));assert any(v[:2]!='00' for v in colours)
                return dict(width=d.width,height=d.height,hotspot=[d.xhot,d.yhot],serial=d.serial,counts=dict(colours),sha256=hashlib.sha256(raw).hexdigest()),raw
            finally:view.x.XFree(image)
        try:
            geo=re.fullmatch(rb'\x1b\[6;(\d+);(\d+)t',emit('geometry',CSI+b'16t'));assert geo
            cw,ch=int(geo[2]),int(geo[1]);windows=view.windows();view.window=max((w for w in windows if (w['width'],w['height'])==(80*cw+4,24*ch+4)),key=lambda w:w['depth'])['window'];view.action(('move',8,5),(cw,ch))
            for index,(stage,wire) in enumerate(STEPS):
                response=emit(stage,wire);d,raw=cursor();file=f'{index:02d}-{stage}.argb';(folder/file).write_bytes(raw)
                transcript['steps'].append(dict(stage=stage,sequence_hex=wire.hex(),reply_hex=response.hex(),cursor=dict(**d,file=file)));write(folder/'observed.json',transcript)
            write(control,dict(stop=True));assert process.wait(timeout=5)==0
            transcript['completed']=True
        finally:
            if process.poll() is None:
                write(control,dict(stop=True))
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
            transcript['exit_code']=process.returncode;write(folder/'observed.json',transcript);view.close()
    return transcript

def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise SystemExit('Use the GitHub-hosted pointer-colour reference workflow')
    if sys.argv[1:2]==['--child']:return child(*map(Path,sys.argv[2:4]))
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--xterm',required=True,type=Path);p.add_argument('--directory',required=True,type=Path);args=p.parse_args();args.directory.mkdir()
    rd,wr=os.pipe();server=subprocess.Popen(['Xvfb','-displayfd',str(wr),'-screen','0','1024x768x24','-nolisten','tcp'],pass_fds=[wr]);os.close(wr)
    try:
        with os.fdopen(rd,'rb') as pipe:display=':'+pipe.readline().decode().strip();assert re.fullmatch(r':\d+',display)
        meta=dict(xterm_sha256=hashlib.sha256(args.xterm.read_bytes()).hexdigest(),version=subprocess.check_output([str(args.xterm),'-version'],text=True).strip(),profiles={})
        for name,params in PROFILES.items():
            result=run(args.xterm,display,args.directory,name,params);meta['profiles'][name]=len(result['steps']);print(name,meta['profiles'][name],flush=True)
        write(args.directory/'identity.json',meta)
    finally:server.terminate();server.wait(timeout=5)

if __name__=='__main__':main()
