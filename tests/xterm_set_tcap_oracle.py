"""Observe XTSETTCAP queries and real key output on an isolated Xvfb display.

No expected database contents are generated from Nemoterm. Raw replies, absence
of replies, input actions, selected terminfo entries and cleanup are retained.
"""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
from xterm_locator_oracle import Display,write
from xterm_udk_oracle import capture_case,prepare_keyboard,step

E=b'\x1b';C=E+b'[';ST=E+b'\\'
TERMS=('vt100','vt220','vt525','linux','xterm','xterm-256color','screen','screen-256color',
       'tmux','tmux-256color','dumb','rxvt-unicode-256color','alacritty','xterm-kitty')
KEYS=('F1','F5','F12','Up','Home','Insert','Delete','Prior','KP_Enter')
QUERY=E+b'P+q'+b';'.join(n.hex().encode() for n in
    (b'TN',b'Co',b'k1',b'k5',b'ku',b'kh',b'kI',b'kD',b'kP',b'kent'))+ST

def setting(name):return E+b'P+p'+name.hex().encode()+ST

def cases(available):
    result={}
    resources=['-xrm','XTerm*VT100.translations: #replace\\n<KeyPress>: insert-seven-bit()']
    for term in available:
        result['startup-'+term]=dict(profile='tcap',resources=resources+['-tn',term],
            steps=[step(QUERY)]+[step(key=key,modifiers=()) for key in KEYS])
    for profile in ('default','tcap'):
        result[profile+'-control']=dict(profile=profile,resources=resources,
            steps=[step(QUERY),step(key='F1',modifiers=()),step(key='Up',modifiers=())])
        for term in TERMS:
            sequence=[step(QUERY),step(setting(term.encode())+QUERY)]
            sequence += [step(key=key,modifiers=()) for key in KEYS]
            sequence += [step(key='F1',modifiers=('Shift_L',)),
                         step(C+b'?1h',key='Up',modifiers=()),
                         step(setting(b'xterm-256color')+QUERY,key='F1',modifiers=())]
            result[profile+'-'+term]=dict(profile=profile,resources=resources,steps=sequence)
    payloads=(b'',b'not-a-terminal-nemo-20261116',b'VT100',b'vt100 ',b'vt100\0junk',
              b'vt100;linux',b'vt100|linux',b'vt100/..',b'vt100\\x',b'vt100:linux',
              b'vt100,linux',b'vt100\t',b'\x01',b'\xff',b'a'*31,b'a'*32)
    for index,value in enumerate(payloads):
        result['invalid-name-'+str(index)]=dict(profile='tcap',resources=resources,
            steps=[step(QUERY,key='Up',modifiers=()),step(setting(value)+QUERY,key='Up',modifiers=())])
    for value in (b'7',b'7674313030x',b'7674313030;6c696e7578',b'zz',b'7674313030=31'):
        result['invalid-hex-'+value.hex()]=dict(profile='tcap',resources=resources,
            steps=[step(QUERY,key='Up',modifiers=()),step(E+b'P+p'+value+ST+QUERY,key='Up',modifiers=())])
    for name,reset in [('ris',E+b'c'),('soft',C+b'!p'),('level',C+b'63;1"p'),
                       ('alternate',C+b'?1049h'+C+b'?1049l'),('cursor',E+b'7'+E+b'8')]:
        result['lifetime-'+name]=dict(profile='tcap',resources=resources,
            steps=[step(setting(b'linux')+QUERY,key='F1',modifiers=()),
                   step(reset+QUERY,key='F1',modifiers=())])
    for name,extra in [('master-denied',['allowTcapOps:false']),
                       ('setter-denied',['allowTcapOps:false','disallowedTcapOps:SetTcap']),
                       ('getter-denied',['allowTcapOps:false','disallowedTcapOps:GetTcap']),
                       ('master-override',['allowTcapOps:true','disallowedTcapOps:SetTcap'])]:
        args=resources+sum((['-xrm','XTerm*'+r] for r in extra),[])
        result['policy-'+name]=dict(profile='tcap',resources=args,
            steps=[step(QUERY,key='Up',modifiers=()),step(setting(b'linux')+QUERY,key='Up',modifiers=())])
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--xterm',required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();folder=args.output.with_suffix('');folder.mkdir(exist_ok=False)
    entries={}
    for term in TERMS:
        run=subprocess.run(['infocmp','-1','-x',term],capture_output=True)
        entries[term]=dict(exit_code=run.returncode,stdout=run.stdout.decode(),stderr=run.stderr.decode())
    r,w=os.pipe()
    server=subprocess.Popen(['Xvfb','-displayfd',str(w),'-screen','0','1024x768x24','-nolisten','tcp'],
        pass_fds=[w],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    os.close(w);display=':'+os.read(r,100).decode().strip();os.close(r)
    owner=Display(display)
    subprocess.run(['setxkbmap','-display',display,'-option','','-option','srvrkeys:none'],check=True)
    result=dict(completed=False,executable_sha256=hashlib.sha256(Path(args.xterm).read_bytes()).hexdigest(),
        version=subprocess.check_output([args.xterm,'-version'],text=True).strip(),
        ncurses_version=subprocess.check_output(['infocmp','-V'],text=True).strip(),terminfo=entries,
        fixtures={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
                  for n in ('xterm_set_tcap_oracle.py','xterm_udk_oracle.py','xterm_locator_oracle.py')},cases={})
    try:
        result['private_keyboard']=prepare_keyboard(owner)
        for name,spec in cases([t for t,v in entries.items() if v['exit_code']==0]).items():
            value=capture_case(args.xterm,display,name,spec,folder)
            result['cases'][name]=value;write(args.output,result)
            assert value['completed'] and value['exit_code']==0 and not value['stderr'],name
            if name=='default-control':
                assert bytes.fromhex(value['steps'][1]['reply_hex'])==b'\x1bOP'
                assert bytes.fromhex(value['steps'][2]['reply_hex'])==b'\x1b[A'
            print(name,len(value['steps']),flush=True)
        result['completed']=True
    finally:
        write(args.output,result);owner.close();server.terminate();server.wait(timeout=5)

if __name__=='__main__':main()
