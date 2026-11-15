"""Capture OSC 60/61/62 against pinned, unmodified XTerm on private Xvfb.

Queries are authored inputs. Replies remain raw observations; only three small
literal controls check that the collector actually observes resource policy.
"""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time
from xterm_locator_oracle import child, read, write, MARKER

E=b'\x1b';C=E+b'[';ST=E+b'\\';OSC=E+b']'
CATEGORIES=('allowColorOps','allowFontOps','allowMouseOps','allowPasteControls',
            'allowTcapOps','allowTitleOps','allowWindowOps')

def query(number,payload=b'',ending=ST):
    return OSC+str(number).encode()+(b';'+payload if payload is not None else b'')+ending

def cases():
    result={'literal-barrier':b''}
    for ending_name,ending in [('st',ST),('bel',b'\x07')]:
        for i,payload in enumerate((None,b'',b'?',b'ignored',b'allowColorOps')):
            result[f'allowed-{ending_name}-{i}']=query(60,payload,ending)
        names=(*CATEGORIES,'allowWinOps','','?','unknown','allowColor','ALLOWCOLOROPS',
               'allowcolorops',' allowColorOps','allowColorOps ','allowColorOps;?',
               'allowColorOps,allowFontOps')
        for number in (61,62):
            for i,name in enumerate(names):
                result[f'category-{number}-{ending_name}-{i}']=query(number,name.encode(),ending)
            result[f'bare-{number}-{ending_name}']=query(number,None,ending)
    result['leading-zero']=OSC+b'060;?'+ST+OSC+b'061;allowMouseOps'+ST+OSC+b'062;allowWindowOps'+ST
    result['chained']=query(60)+query(61,b'allowColorOps')+query(62,b'allowColorOps')
    result['query-does-not-set']=query(60,b'allowColorOps:false')+query(60)
    result['category-tab']=query(62,b'allowColor\tOps')
    result['category-nul']=query(62,b'allowColor\x00Ops')
    result['category-high-byte']=query(62,b'allowColor\xffOps')
    for code,name in [(b'\x18','can'),(b'\x1a','sub')]:
        result['cancel-'+name]=OSC+b'62;allowColor'+code+ST+query(60)
    result['escape-restart']=OSC+b'62;allowColor'+query(60)
    result['c1-output']=E+b' G'+query(60)+query(62,b'allowColorOps')+E+b' F'
    result['raw-c1-utf8']=b'\x9d62;allowColorOps\x9c'+query(60)
    result['utf8-encoded-c1']=b'\xc2\x9d62;allowColorOps\xc2\x9c'+query(60)
    for name,prefix in [('ris',E+b'c'),('soft',C+b'!p'),('level',C+b'65;1"p'),
                        ('alt',C+b'?1049h'),('main',C+b'?1049l'),('vt52-return',C+b'?2l'+E+b'<')]:
        result['lifecycle-'+name]=prefix+query(60)+query(61,b'allowWindowOps')+query(62,b'allowWindowOps')
    return result

def profiles():
    on={name:'true' for name in CATEGORIES};off={name:'false' for name in CATEGORIES}
    result={'default':{},'all-on':on,'all-off':off}
    for name in CATEGORIES:
        result['only-'+name]={**off,name:'true'}
        result['except-'+name]={**on,name:'false'}
    custom={'disallowedColorOps':'SetColor,GetAnsiColor','disallowedFontOps':'GetFont',
            'disallowedMouseOps':'X10,FocusEvent,SGR','disallowedPasteControls':'C0,DEL',
            'disallowedTcapOps':'SetTcap','disallowedWindowOps':'SetWinSizeChars,GetSelection,SetSelection'}
    result['custom-disabled']={**off,**custom}
    result['custom-enabled']={**on,**custom}
    result['no-subcategories']={**off,**{name:'' for name in custom}}
    return result

def capture(xterm,display,name,resources,base):
    folder=base/name;folder.mkdir()
    report,control=folder/'child.json',folder/'control.json'
    argv=[xterm,'-geometry','80x24','-fn','6x13','-ti','vt525','-u8']
    for key,value in resources.items():argv+=['-xrm',f'*{key}: {value}']
    argv+=['-e',sys.executable,str(Path(__file__).resolve()),'--child',str(report),str(control)]
    terminal=subprocess.Popen(argv,env=dict(os.environ,DISPLAY=display,LC_ALL='C.UTF-8',XENVIRONMENT='/dev/null'),
                              stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    result=dict(completed=False,resources=resources,argv=argv,cases={},forced_cleanup=False)
    try:
        deadline=time.monotonic()+5
        while not report.exists() and time.monotonic()<deadline:
            assert terminal.poll() is None
            time.sleep(.01)
        assert report.exists()
        for index,(case,sequence) in enumerate(cases().items(),1):
            # Force only the final DSR barrier back to seven-bit output. The
            # query's own response bytes (including C1 framing) remain intact.
            wire=sequence+E+b' F'+C+b'5n'
            write(control,dict(id=index,phase=case,hex=wire.hex()))
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                snapshot=read(report);received=bytes.fromhex(snapshot.get('hex',''))
                if (snapshot.get('phase')==case and snapshot.get('command_id')==index and received.endswith(MARKER)):
                    break
                assert terminal.poll() is None,(name,case,terminal.returncode)
                time.sleep(.005)
            else:raise AssertionError((name,case,read(report)))
            time.sleep(.025)
            late=read(report)
            assert late.get('phase')==case and late.get('hex')==received.hex(),(name,case,'late response',late)
            result['cases'][case]=dict(sequence_hex=sequence.hex(),input_with_barrier_hex=wire.hex(),
                reply_hex=received[:-len(MARKER)].hex(),wire_with_barrier_hex=received.hex())
        result['completed']=True
    finally:
        write(control,dict(stop=True))
        try:terminal.wait(timeout=3)
        except subprocess.TimeoutExpired:
            result['forced_cleanup']=True;terminal.terminate();terminal.wait(timeout=3)
        result['exit_code']=terminal.returncode
        result['stderr']=terminal.stderr.read().decode('utf-8',errors='replace')
        write(folder/'observed.json',result)
    assert result['exit_code']==0 and not result['forced_cleanup'] and not result['stderr'],result
    return result

def main():
    if len(sys.argv)>1 and sys.argv[1]=='--child':return child(*map(Path,sys.argv[2:4]))
    assert os.environ.get('GITHUB_ACTIONS')=='true','Reference runs only on disposable cloud runners'
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();output=Path(args.output);base=output.with_suffix('');base.mkdir()
    r,w=os.pipe()
    xvfb=subprocess.Popen(['Xvfb','-displayfd',str(w),'-screen','0','1024x768x24','-nolisten','tcp'],
                          pass_fds=[w],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    os.close(w);display=':'+os.read(r,100).decode().strip();os.close(r)
    result=dict(completed=False,version=subprocess.check_output([args.xterm,'-version'],text=True).strip(),
        executable_sha256=hashlib.sha256(Path(args.xterm).read_bytes()).hexdigest(),
        fixture_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),profiles={})
    try:
        for name,resources in profiles().items():
            result['profiles'][name]=capture(args.xterm,display,name,resources,base);write(output,result)
            print(name,len(result['profiles'][name]['cases']),'raw reply streams retained',flush=True)
        off=result['profiles']['all-off']['cases'];on=result['profiles']['all-on']['cases']
        assert off['allowed-st-1']['reply_hex']==(OSC+b'60'+ST).hex()
        assert on['allowed-st-1']['reply_hex']==(OSC+b'60;'+','.join(CATEGORIES).encode()+ST).hex()
        assert on['category-62-st-10']['reply_hex']==(OSC+b'62'+ST).hex()
        result['literal_controls']=['all-off-empty','all-on-seven-categories','unknown-empty']
        result['completed']=True
    finally:
        write(output,result);xvfb.terminate();xvfb.wait(timeout=5)

if __name__=='__main__':main()
