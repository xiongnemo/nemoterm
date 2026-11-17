"""Observe resource 0 and legacy/VT220 dispatch on an isolated Xvfb keyboard."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
import xterm_udk_oracle as harness
from xterm_extended_keys_oracle import ObservedDisplay,prepare_keyboard,RESOURCES
from xterm_locator_oracle import write

C=b'\x1b['
MASKS=(0,1,2,4,8,15)
MODIFIERS=[tuple(name for bit,name in ((1,'Shift_L'),(2,'Alt_L'),(4,'Control_L')) if mask&bit)
           for mask in range(8)]

def cases():
    result={}
    def add(name,steps,profile='default',locks=0):
        result[name]=dict(profile=profile,resources=RESOURCES,locks=locks,steps=steps)
    def step(sequence=b'',key=None,mods=0):
        return dict(**harness.step(sequence,key,MODIFIERS[mods]),requested_key=key,modifiers=mods)
    add('control-default-function',[step(key='F1')])
    add('control-legacy-function',[step(key='F1')],profile='legacy')
    add('control-vt220-udk',[step(harness.dcs(b'17/414243'),'F6',1)],profile='vt220')
    add('control-resource0',[step(C+b'?0m')])
    keys=('Up','Home','Insert','Delete','Prior','F1','F6','F12','F20',
          'KP_Enter','KP_Add','KP_Divide','KP_1','Help','Menu','Print')
    for profile in ('default','legacy','vt220'):
        for key in keys:
            add(profile+'-'+key,[step(C+f'>0;{mask}m'.encode()+C+b'?0m',key,mods)
                                for mask in MASKS for mods in range(8)],profile)
        for key in ('KP_1','KP_Add','KP_Enter'):
            add(profile+'-application-'+key,[step(b'\x1b='+C+f'>0;{mask}m'.encode(),key,mods)
                for mask in (0,1,15) for mods in range(8)],profile)
        add(profile+'-numlock',[step(b'\x1b='+C+f'>0;{mask}m'.encode(),'KP_1',mods)
            for mask in (0,1,15) for mods in (0,2,4,6)],profile,16)
        for resource,key in ((1,'Up'),(2,'F6'),(3,'KP_Enter'),(6,'Shift_L'),(7,'Escape')):
            add(profile+'-extended-'+str(resource),[step(C+f'>0;{mask}m'.encode()+
                C+f'>{resource};4m'.encode(),key,mods) for mask in (0,15) for mods in (0,2,4,6)],profile)
        add(profile+'-udk',[step(harness.dcs(b'17/41;32/42')+C+f'>0;{mask}m'.encode(),
            'F6',mods) for mask in (0,4,15) for mods in range(8)],profile)
        add(profile+'-udk-extended',[step(harness.dcs(b'17/41;32/42')+C+b'>2;4m',
            'F6',mods) for mods in (0,1,4,5)],profile)
        add(profile+'-mok-override',[step(C+b'>0;0m'+C+f'>4;{level}m'.encode(),key,mods)
            for level in (0,1,2,3) for key in ('Up','F6','KP_Enter') for mods in (1,4,6)],profile)
    query=C+b'?0;1;2;3;4;6;7m'+C+b'>0g'+b'\x1bP$q>0m\x1b\\'+b'\x1bP$q>0f\x1b\\'
    add('state-values',[step(C+f'>0;{v}m'.encode()+query) for v in (0,1,2,4,8,15,16,255,65535)])
    add('state-formats',[step(C+f'>0;{v}f'.encode()+query) for v in (0,1,2,4,15,65535)])
    for name,reset in [('ris',b'\x1bc'),('soft',C+b'!p'),('level',C+b'63;1"p'),
        ('one',C+b'>0m'+C+b'>0f'),('all',C+b'>m'+C+b'>f'),('disable',C+b'>0n'),
        ('alternate',C+b'?1049h'+C+b'?1049l'),('cursor',b'\x1b7\x1b8')]:
        add('state-'+name,[step(C+b'>0;15:5m'+C+b'>0;1f'+reset+query)])
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--profile',choices=('all','default','legacy','vt220'),default='all')
    args=parser.parse_args();output=Path(args.output);folder=output.with_suffix('');folder.mkdir(exist_ok=False)
    r,w=os.pipe()
    xvfb=subprocess.Popen(['Xvfb','-displayfd',str(w),'-screen','0','1024x768x24','-nolisten','tcp'],
        pass_fds=[w],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    os.close(w);display=':'+os.read(r,100).decode().strip();os.close(r)
    owner=ObservedDisplay(display);harness.Display=ObservedDisplay
    subprocess.run(['setxkbmap','-display',display,'-option','','-option','srvrkeys:none'],check=True)
    specs=cases()
    if args.profile!='all':
        # Every case already owns a fresh XTerm. Retain all literal and state
        # controls in each shard; only independent profile cases are partitioned.
        specs={name:spec for name,spec in specs.items() if name.startswith(
            ('control-','state-',args.profile+'-'))}
    names={a[1] for spec in specs.values() for s in spec['steps'] for a in s['actions']}
    result=dict(completed=False,version=subprocess.check_output([args.xterm,'-version'],text=True).strip(),
        executable_sha256=hashlib.sha256(Path(args.xterm).read_bytes()).hexdigest(),
        requested_profile=args.profile,
        fixtures={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [Path(__file__),*[Path(__file__).with_name(n) for n in ('xterm_udk_oracle.py',
                'xterm_extended_keys_oracle.py','xterm_locator_oracle.py')]]},cases={})
    controls={'control-default-function':[b'\x1bOP'],'control-legacy-function':[b'\x1b[11~'],
        'control-vt220-udk':[b'ABC'],'control-resource0':[b'\x1b[>0;0m']}
    try:
        result['private_keyboard']=prepare_keyboard(owner,names)
        for name,spec in specs.items():
            assert owner.x.XkbLockModifiers(owner.d,256,18,spec['locks'])
            owner.x.XSync(owner.d,False)
            observed=harness.capture_case(args.xterm,display,name,spec,folder)
            observed['requested_locks']=spec['locks'];result['cases'][name]=observed;write(output,result)
            assert observed['completed'] and observed['exit_code']==0
            if name in controls:
                assert [bytes.fromhex(s['reply_hex']) for s in observed['steps']]==controls[name],name
            print(name,len(observed['steps']),flush=True)
        result['literal_controls']=list(controls);result['completed']=True
    finally:
        write(output,result);owner.close();xvfb.terminate();xvfb.wait(timeout=5)

if __name__=='__main__':main()
