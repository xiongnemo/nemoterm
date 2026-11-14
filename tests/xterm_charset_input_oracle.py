"""Capture input bytes from a fresh owned XTerm on a private Xvfb display.

Only that isolated X server receives XSendEvent keys and selection data.
Neither the Windows desktop nor its clipboard is accessed.
"""
import argparse,hashlib,json,os,select,shutil,subprocess,sys,tempfile,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
TEXT='\u00a3\u00c4\u00d6\u00df\u00e9\u20ac\u4e2d'
KEYS=['sterling','Adiaeresis','Odiaeresis','ssharp','eacute','EuroSign','U4E2D']
MODES={
    'utf8':'\x1b%G',
    'docs-byte':'\x1b%G\x1b%@',
    'docs-utf8-restored':'\x1b%@\x1b%G',
    'nrc-ascii':'\x1b%G\x1b[?42h',
    'nrc-british':'\x1b%G\x1b[?42h\x1b(A',
    'nrc-german':'\x1b%G\x1b[?42h\x1b(K',
    'nrc-german-g1':'\x1b%G\x1b[?42h\x1b)K\x0e',
    'nrc-dutch':'\x1b%G\x1b[?42h\x1b(4',
    'nrc-greek':'\x1b%G\x1b[?42h\x1b(\">',
    'nrc-off':'\x1b%G\x1b[?42h\x1b(K\x1b[?42l',
}

def read(path):
    try:return json.loads(path.read_text())
    except (FileNotFoundError,ValueError):return {}

def wait(fn,timeout=5):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        result=fn()
        if result:return result
        time.sleep(.01)
    raise AssertionError('timed out waiting for owned reference')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm',type=Path,default=Path('/tmp/nemoterm-xterm-reference/xterm'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--paste-only',action='store_true')
    parser.add_argument('--text',default=TEXT)
    parser.add_argument('--text-file',type=Path)
    parser.add_argument('--all-sets',action='store_true')
    parser.add_argument('--upss-only',action='store_true')
    args=parser.parse_args()
    if args.text_file:args.text=args.text_file.read_text()
    modes=dict(MODES)
    if args.upss_only:
        assert not args.all_sets
        from xterm_upss_oracle import ASSIGNMENTS
        modes={}
        for level in (3,5):
            for size,designation in ASSIGNMENTS:
                modes[f'upss-{level}-{size}-{designation.encode().hex()}']=(
                    f'\x1b[{60+level};1"p\x1b%G\x1b[?42h\x1bP{size}!u{designation}\x1b\\\x1b(<')
    if args.all_sets:
        from xterm_charsets_oracle import SETS_94,SETS_96
        for designation in SETS_94:
            modes['94-'+designation.encode().hex()]='\x1b%G\x1b[?42h\x1b('+designation
        for designation in SETS_96:
            modes['96-'+designation.encode().hex()]='\x1b%G\x1b[?42h\x1b-'+designation+'\x0e'
        modes['level2-dec-supp']='\x1b[62;1"p\x1b%G\x1b[?42h\x1b(<'
        modes['level3-jis-roman']='\x1b[63;1"p\x1b%G\x1b[?42h\x1b(J'
        modes['level3-jis-katakana']='\x1b[63;1"p\x1b%G\x1b[?42h\x1b(I'
    for tool in ['Xvfb','xdotool','xclip']:
        if not shutil.which(tool):raise SystemExit('missing '+tool)
    results=dict(version=subprocess.check_output([str(args.xterm),'-version'],text=True).strip(),
        executable_sha256=hashlib.sha256(args.xterm.read_bytes()).hexdigest(),
        text=args.text,keys=[] if args.paste_only else KEYS,
        transport='fresh private Xvfb/XTerm, XSendEvent and PRIMARY selection',cases={})
    for name,setup in modes.items():
        with tempfile.TemporaryDirectory(prefix='nemoterm-charset-input-') as temporary:
            folder=Path(temporary);report=folder/'report.json';control=folder/'control.json'
            r,w=os.pipe()
            xvfb=subprocess.Popen(['Xvfb','-displayfd',str(w),'-screen','0','1024x768x24','-nolisten','tcp'],
                pass_fds=[w],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            os.close(w);terminal=None;clip=None
            try:
                assert select.select([r],[],[],5)[0], 'Xvfb display allocation timeout'
                display=os.read(r,100).decode().strip();os.close(r);r=None
                env=dict(os.environ,DISPLAY=':'+display)
                terminal=subprocess.Popen([str(args.xterm),'-ti','vt525','-geometry','80x24',
                    '-xrm','*allowSendEvents: true','-xrm','*locale: false','-xrm','*wideChars: true',
                    '-e',sys.executable,str(ROOT/'xterm_mok_child.py'),str(report),str(control)],
                    env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                wait(report.exists)
                window=wait(lambda:subprocess.run(['xdotool','search','--pid',str(terminal.pid)],
                    env=env,capture_output=True,text=True).stdout.strip()).splitlines()[-1]
                sequence=0
                def phase(text=''):
                    nonlocal sequence
                    sequence+=1
                    tmp=control.with_suffix('.tmp')
                    tmp.write_text(json.dumps(dict(phase=sequence,sequence=text)))
                    tmp.replace(control)
                    wait(lambda:read(report).get('phase')==sequence)
                phase(setup+'\x1b[5n')
                wait(lambda:read(report).get('hex','').endswith('1b5b306e'))
                def key(chord):
                    phase()
                    subprocess.run(['xdotool','key','--window',window,'--delay','1',chord],env=env,
                        check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    previous=None;changed=time.monotonic();end=changed+2
                    while time.monotonic()<end:
                        value=read(report).get('hex','')
                        if value!=previous:previous=value;changed=time.monotonic()
                        if time.monotonic()-changed>.1:return value
                        time.sleep(.01)
                    raise AssertionError('owned input did not settle')
                result=dict(setup=setup,key_hex={} if args.paste_only else {keyname:key(keyname) for keyname in KEYS})
                clip=subprocess.Popen(['xclip','-selection','primary','-in','-quiet'],env=env,
                    stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                clip.stdin.write(args.text.encode());clip.stdin.close()
                wait(lambda:subprocess.run(['xclip','-selection','primary','-out'],env=env,
                    stdout=subprocess.PIPE,stderr=subprocess.DEVNULL).stdout==args.text.encode())
                result['paste_hex']=key('shift+Insert')
                results['cases'][name]=result
                args.output.write_text(json.dumps(results,indent=2)+'\n')
                print(name,result,flush=True)
            finally:
                if r is not None:os.close(r)
                for proc in [clip,terminal,xvfb]:
                    if proc is not None:
                        proc.terminate();proc.wait(timeout=5)

if __name__=='__main__':main()
