"""Optional Linux/Xvfb reference capture, using only its isolated X server.

Build the pinned xterm revision documented in research/modify-other-keys.md.
Run: python3 tests/xterm_mok_reference.py --xterm /path/to/xterm
"""
import argparse, hashlib, json, os, select, subprocess, sys, tempfile, time
from pathlib import Path
root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--xterm',required=True,type=Path)
parser.add_argument('--output',type=Path,default=root.parent/'research/xterm-mok-reference.json')
options=parser.parse_args()
executable=options.xterm.resolve(strict=True)
if not os.access(executable,os.X_OK):
    parser.error('--xterm must name an executable file')
resources=['*allowSendEvents:true','*metaSendsEscape:true','*altSendsEscape:true','*backarrowKey:false']
def wait(fn):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        value=fn()
        if value: return value
        time.sleep(.01)
    raise AssertionError('timeout')
def read(path):
    try: return json.loads(path.read_text())
    except (FileNotFoundError,ValueError): return {}
with tempfile.TemporaryDirectory(prefix='nemoterm-xterm-') as temporary:
    folder=Path(temporary); report=folder/'report.json'; control=folder/'control.json'
    r,w=os.pipe()
    xvfb=subprocess.Popen(['Xvfb','-displayfd',str(w),'-screen','0','1024x768x24','-nolisten','tcp'],pass_fds=[w],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    os.close(w)
    if not select.select([r],[],[],5)[0]:
        xvfb.terminate(); xvfb.wait(timeout=3); os.close(r)
        raise RuntimeError('Xvfb did not allocate an isolated display')
    display=os.read(r,100).decode().strip(); os.close(r)
    env=dict(os.environ, DISPLAY=':'+display)
    try:
        with (folder/'xterm.log').open('w') as log:
            terminal=subprocess.Popen([str(executable),*[arg for resource in resources for arg in ('-xrm',resource)],
                '-geometry','80x24',
                '-e',sys.executable,str(root/'xterm_mok_child.py'),str(report),str(control)],env=env,
                stdout=subprocess.DEVNULL,stderr=log)
    except BaseException:
        xvfb.terminate(); xvfb.wait(timeout=3)
        raise
    sequence=0
    def phase(text=''):
        global sequence
        sequence+=1
        temporary=control.with_suffix('.tmp'); temporary.write_text(json.dumps({'phase':sequence,'sequence':text})); temporary.replace(control)
        wait(lambda:read(report).get('phase')==sequence)
        time.sleep(.025)
        return read(report)
    def probe(text):
        phase(text)
        try: return wait(lambda:read(report).get('hex'))
        except AssertionError:
            print('No reply for',repr(text),read(report),flush=True)
            return ''
    def key(chord):
        phase()
        subprocess.run(['xdotool','key','--window',window,'--delay','1',chord],env=env,check=True,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        previous=None; changed=time.monotonic(); deadline=changed+2
        while time.monotonic()<deadline:
            value=read(report).get('hex','')
            if value!=previous: previous=value; changed=time.monotonic()
            if time.monotonic()-changed>.08: break
            time.sleep(.01)
        return bytes.fromhex(previous).decode('utf-8',errors='strict')
    try:
        wait(lambda:report.exists())
        window=wait(lambda:subprocess.run(['xdotool','search','--pid',str(terminal.pid)],env=env,capture_output=True,text=True).stdout.strip()).splitlines()[-1]
        results={'source_commit':'5c75ead9a75d4b2e666ca06fa94503b5766ed93f',
                 'executable_sha256':hashlib.sha256(executable.read_bytes()).hexdigest(),
                 'version':subprocess.check_output([str(executable),'-version'],text=True).strip(),
                 'resources':resources, 'transport':'isolated Xvfb, XSendEvent via xdotool', 'keys':{}}
        chords=['a','shift+a','ctrl+a','ctrl+shift+a','alt+a','alt+shift+a','ctrl+alt+a',
                '1','shift+1','ctrl+1','ctrl+shift+1','ctrl+2','ctrl+shift+2','ctrl+3','ctrl+slash',
                'ctrl+period','space','shift+space','ctrl+space','alt+space',
                'Tab','shift+Tab','ctrl+Tab','alt+Tab','Return','shift+Return','ctrl+Return','alt+Return',
                'BackSpace','shift+BackSpace','ctrl+BackSpace','alt+BackSpace','Escape','ctrl+Escape',
                'F1','ctrl+F1','Up','shift+Up','KP_1','ctrl+alt+period','ctrl+shift+bracketleft',
                'alt+shift+Tab','ctrl+shift+Tab','shift+Escape','shift+semicolon','shift+bracketleft',
                'ctrl+asciicircum','ctrl+grave','ctrl+minus','ctrl+shift+minus']
        for level in range(4):
            probe(f'\x1b[>4;{level}m\x1b[?4m')
            results['keys'][str(level)]={chord:key(chord) for chord in chords}
        results['queries']={}
        for name,seq in {
            'disable':'\x1b[>4n\x1b[?4m',
            'format':'\x1b[>4;1f\x1b[>4g',
            'mask-second':'\x1b[>4;2:1m\x1b[?4m',
            'mask-first':'\x1b[>4:4m\x1b[?4m',
            'rqss-level':'\x1bP$q>4m\x1b\\',
            'rqss-format':'\x1bP$q>4f\x1b\\',
            'alt-screen':'\x1b[?1049h\x1b[?4m\x1b[?1049l',
        }.items():
            results['queries'][name]=bytes.fromhex(probe(seq)).decode()
            print(name,repr(results['queries'][name]),flush=True)
        results['masks']={}
        for level in (1,2,3):
            for mask in (0,1,4,5,8):
                probe(f'\x1b[>4;{level}:{mask}m\x1b[?4m')
                results['masks'][f'{level}:{mask}']={chord:key(chord) for chord in ['a','shift+a','ctrl+a','ctrl+shift+a','alt+a','ctrl+period','ctrl+shift+1']}
        output=options.output; output.write_text(json.dumps(results,indent=2))
        print(output)
    finally:
        try:
            terminal.terminate(); terminal.wait(timeout=3)
        finally:
            xvfb.terminate(); xvfb.wait(timeout=3)
