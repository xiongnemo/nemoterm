"""Capture XTerm's real clipboard paste bytes and independent mode queries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

CSI = '\x1b['
QUERY = CSI+'?2004$p'+CSI+'?2006$p'
TEXT = 'A中\tB\n\nC😀\n|END.'
DSR = b'\x1b[5n'
ACK = b'\x1b[0n'
STAGES = {
    'default':'', 'restore-before-save':CSI+'?2004;2006r', 'lf':CSI+'?2006h',
    'both':CSI+'?2004h', 'save-both':CSI+'?2004;2006s', 'off':CSI+'?2004;2006l',
    'restore-lf':CSI+'?2006r', 'restore-bracket':CSI+'?2004r',
    'bracket-only':CSI+'?2006l', 'alternate':CSI+'?1049h',
    'alt-lf':CSI+'?2006h', 'back':CSI+'?1049l', 'soft-reset':CSI+'!p',
    'after-soft-restore':CSI+'?2006r', 'on-before-ris':CSI+'?2004;2006h',
    'hard-reset':'\x1bc', 'after-ris-restore':CSI+'?2004;2006r',
}


def child(path):
    import select
    import time
    import tty
    tty.setraw(0)
    window = os.environ['WINDOWID']
    subprocess.run(['xdotool','windowfocus','--sync',window],check=True,timeout=5)
    def read_until(end):
        b=bytearray(); stop=time.monotonic()+5
        while end not in b:
            delay=stop-time.monotonic()
            if delay <= 0 or not select.select([0],[],[],delay)[0]: raise TimeoutError((end,b.hex()))
            b.extend(os.read(0,4096))
        return bytes(b)
    results={}
    try:
        for name, change in STAGES.items():
            row=results[name]={'sequence':change+QUERY}
            os.write(1,(change+QUERY).encode()+DSR); modes=read_until(ACK); assert modes.endswith(ACK)
            row['mode_hex']=modes[:-len(ACK)].hex()
            subprocess.run(['xdotool','key','F6'],check=True,timeout=4)
            first=read_until(b'|END.'); os.write(1,DSR); tail=read_until(ACK); assert tail.endswith(ACK)
            row['paste_hex']=(first+tail[:-len(ACK)]).hex()
        completed=True
    except BaseException as exc:
        path.write_text(json.dumps(dict(completed=False,error=repr(exc),cases=results),indent=2)); raise
    path.write_text(json.dumps(dict(completed=completed,clipboard_hex=TEXT.encode().hex(),cases=results),indent=2))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--xterm');parser.add_argument('--child',action='store_true');parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    if args.child:child(args.output);return
    data=TEXT.encode(); env=dict(os.environ, LC_ALL='C.UTF-8');args.output.parent.mkdir(parents=True,exist_ok=True)
    owner=subprocess.Popen(['xclip','-i','-quiet','-selection','clipboard','-target','UTF8_STRING'],env=env,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL)
    try:
        import time
        owner.stdin.write(data);owner.stdin.close();deadline=time.monotonic()+4
        while subprocess.run(['xclip','-o','-selection','clipboard','-target','UTF8_STRING'],env=env,capture_output=True,timeout=2).stdout!=data:
            if time.monotonic()>=deadline:raise AssertionError('X clipboard setup failed')
            time.sleep(.04)
        subprocess.run([args.xterm,'-u8','-geometry','80x24','-xrm','*VT100.Translations: #override\\n<Key>F6: insert-selection(CLIPBOARD)',
            '-e',sys.executable,str(Path(__file__).resolve()),'--child','--output',str(args.output.resolve())],env=env,check=True,timeout=95)
        r=json.loads(args.output.read_bytes());assert r['completed'] and list(r['cases'])==list(STAGES)
        r['xterm_sha256']=hashlib.sha256(Path(args.xterm).read_bytes()).hexdigest(); args.output.write_text(json.dumps(r,indent=2)+'\n')
    finally:
        owner.terminate();owner.wait(timeout=3)


if __name__=='__main__':main()
