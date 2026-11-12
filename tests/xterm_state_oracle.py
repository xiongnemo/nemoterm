"""Independent XTerm oracle for state controls, using a private Xvfb display.

Run under Linux/WSL with Xvfb and an explicitly selected XTerm executable.
No messages or events are sent to the user's desktop.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time


def read(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def write(path, value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


def child(report, control):
    import tty
    tty.setraw(0)
    phase, data = None, b''
    deadline=time.monotonic()+120
    write(report,dict(phase=phase,hex=''))
    while time.monotonic()<deadline:
        command=read(control)
        if command.get('stop'): break
        if command.get('phase')!=phase:
            phase=command['phase'];data=b''
            os.write(1,command['sequence'].encode())
            write(report,dict(phase=phase,hex=''))
        if select.select([0],[],[],.005)[0]:
            data+=os.read(0,65536)
            write(report,dict(phase=phase,hex=data.hex()))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--child',nargs=2)
    parser.add_argument('--xterm',default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output',default='research/state-control-xterm.json')
    args=parser.parse_args()
    if args.child:
        child(*map(Path,args.child));return
    modes=[1,2,3,5,6,7,8,12,25,47,66,80,1000,1001,1002,1003,1004,1005,1006,1007,1015,1016,1049,1070,2004,2026,8452]
    mode_query=''.join(f'\x1b[?{m}$p' for m in modes)
    cpr='\x1b[6n'
    rqss=lambda text:'\x1bP$q'+text+'\x1b\\'
    cases={
        'initial':mode_query+'\x1b[4$p\x1b[12$p\x1b[20$p'+rqss('m')+rqss('r')+rqss(' q'),
        'unsaved-wrap-zero':'\x1b[?7r\x1b[?7$p',
        'soft-main':'\x1bc\x1b[3;12r\x1b[?1;5;6;66;1003;1016;1004;1007;2004h\x1b[4h\x1b[12l\x1b[20h'
                    '\x1b[?7;8;25l\x1b[6 q\x1b[>4;2m\x1b[>4;1f\x1b[5;9H\x1b7'
                    '\x1b[1;2;3;4:3;9;38;2;1;2;3;58;2;4;5;6m\x1b[!p'+mode_query+
                    '\x1b[4$p\x1b[12$p\x1b[20$p\x1b[?4m'+rqss('m')+rqss('r')+rqss(' q')+cpr+'\x1b8'+cpr,
        'soft-alt-saved-main':'\x1bc\x1b[5;6H\x1b7\x1b[?1049h\x1b[9;10H\x1b7\x1b[!p'+cpr+
                              '\x1b[?1049$p\x1b8'+cpr+'\x1b[?1049l'+cpr,
        'soft-palette':'\x1bc\x1b]4;1;?\x07\x1b]10;?\x07\x1b]4;1;#123456\x07\x1b]10;#345678\x07'
                       '\x1b[!p\x1b]4;1;?\x07\x1b]10;?\x07',
        'soft-tab':'\x1bc\x1b[3g\x1b[1;5H\x1bH\x1b[1;1H\x1b[!p\t'+cpr,
        'soft-utf8':'\x1bc\x1b%G\x1b[!p中'+cpr,
        'soft-wrap-pending':'\x1bc\x1b[1;80HX\x1b[!pY'+cpr,
        'origin-home':'\x1bc\x1b[3;12r\x1b[8;9H\x1b[?6h'+cpr+'\x1b[4;5H'+cpr+'\x1b[?6l'+cpr,
        'saved-basic':'\x1bc\x1b[?1;7;25h\x1b[?1;7;25s\x1b[?1;7;25l\x1b[?1;25r'+mode_query,
        'saved-mouse-group':'\x1bc\x1b[?1003;1016h\x1b[?1000;1006s\x1b[?1002;1005h\x1b[?1001;1015r'+mode_query,
        'saved-x10-separate':'\x1bc\x1b[?1003h\x1b[?9s\x1b[?1002h\x1b[?1000s\x1b[?9r'+mode_query,
        'saved-1048-cursor':'\x1bc\x1b[5;6H\x1b[?1048s\x1b[1;2H\x1b[?1048r'+cpr,
        'saved-alt-alias':'\x1bc\x1b[?47h\x1b[?1047s\x1b[?47l\x1b[?1049r\x1b[?47$p',
        'saved-ris-retained':'\x1bc\x1b[?1h\x1b[?1s\x1bc\x1b[?1r\x1b[?1$p',
        'saved-soft-retained':'\x1bc\x1b[?1h\x1b[?1s\x1b[!p\x1b[?1r\x1b[?1$p',
        'saved-overwrite':'\x1bc\x1b[?1h\x1b[?1s\x1b[?1l\x1b[?1s\x1b[?1h\x1b[?1r\x1b[?1$p',
        'saved-origin-home':'\x1bc\x1b[3;12r\x1b[?6h\x1b[?6s\x1b[?6l\x1b[8;9H\x1b[?6r'+cpr,
        'saved-8-ignored':'\x1bc\x1b[?8h\x1b[?8s\x1b[?8l\x1b[?8r\x1b[?8$p',
        'soft-arguments':'\x1bc\x1b[?1h\x1b[123!p\x1b[?1$p',
    }
    with tempfile.TemporaryDirectory(prefix='nemoterm-xterm-state-') as temporary:
        folder=Path(temporary);report=folder/'report.json';control=folder/'control.json'
        r,w=os.pipe()
        xvfb=subprocess.Popen(['Xvfb','-displayfd',str(w),'-screen','0','1024x768x24','-nolisten','tcp'],
                              pass_fds=[w],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        os.close(w);display=os.read(r,100).decode().strip();os.close(r)
        terminal=subprocess.Popen([args.xterm,'-geometry','80x24','-u8','-e',sys.executable,
            str(Path(__file__).resolve()),'--child',str(report),str(control)],
            env=dict(os.environ,DISPLAY=':'+display),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        results=dict(version=subprocess.check_output([args.xterm,'-version'],text=True).strip(),
            executable_sha256=hashlib.sha256(Path(args.xterm).read_bytes()).hexdigest(),cases={})
        try:
            deadline=time.monotonic()+8
            while not report.exists() and time.monotonic()<deadline:time.sleep(.01)
            assert report.exists()
            for name,sequence in cases.items():
                write(control,dict(phase=name,sequence=sequence+'\x1b[5n'))
                deadline=time.monotonic()+8
                while time.monotonic()<deadline:
                    result=read(report)
                    data=bytes.fromhex(result.get('hex',''))
                    if result.get('phase')==name and data.endswith(b'\x1b[0n'):break
                    time.sleep(.01)
                else:raise AssertionError((name,result))
                results['cases'][name]=dict(sequence=sequence,reply=data[:-4].decode())
                print(name,repr(data[:-4].decode()),flush=True)
            Path(args.output).write_text(json.dumps(results,indent=2))
        finally:
            terminal.terminate();terminal.wait(timeout=5)
            xvfb.terminate();xvfb.wait(timeout=5)


if __name__=='__main__':main()
