"""Linux side of the hosted WSL quoted-paste comparison. No model or shell input."""
import hashlib
import json
import os
from pathlib import Path
import select
import sys
import termios
import time
import traceback
import tty

CSI=b'\x1b['; ACK=CSI+b'0n'; QUERY=b''.join(CSI+b'?'+str(v).encode()+b'$p' for v in (2004,2005,2006))
STAGES=[('raw-plain',b''),('raw-quote',CSI+b'?2005h'),('raw-all',CSI+b'?2004;2005;2006h'),('canonical-quote',CSI+b'?2005;2006h')]


def note(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2),encoding='utf-8');tmp.replace(path)


def run(folder,lnext):
    original=termios.tcgetattr(0);out=dict(tty=os.ttyname(0),term=os.environ.get('TERM'),python=sys.version,
        os_release=Path('/etc/os-release').read_text(),fixture_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),cases={})
    # Prove which executable owns our master. WSL's ordinary console input
    # route must not be mistaken for a successful relay fallback.
    if sys.argv[3:]==['--relay-parent']:
        parent=Path('/proc')/str(os.getppid())/'exe'
        out['parent_exe']=os.readlink(parent)
        out['parent_sha256']=hashlib.sha256(parent.read_bytes()).hexdigest()
    def read_piece(end):
        timeout=end-time.monotonic()
        if timeout<=0 or not select.select([0],[],[],timeout)[0]:raise TimeoutError('WSL tty read deadline')
        b=os.read(0,4096)
        if not b:raise EOFError('WSL tty closed')
        return b
    def wait_for_ack(row):
        end=time.monotonic()+12;b=b''
        while not b.endswith(ACK):
            b+=read_piece(end);row['handshake_hex']=b.hex()
        return b[:-len(ACK)]
    try:
        for name,mode in STAGES:
            tty.setraw(0);raw=termios.tcgetattr(0);raw[6][termios.VLNEXT]=bytes([lnext]);termios.tcsetattr(0,termios.TCSANOW,raw)
            r=out['cases'][name]={'chunks':[],'handshake_hex':''}
            os.write(1,CSI+b'?2004;2005;2006l'+mode+QUERY+CSI+b'5n')
            r['mode_hex']=wait_for_ack(r).hex()
            canonical=name.startswith('canonical')
            if canonical:
                raw[3]|=termios.ICANON|termios.IEXTEN;raw[0]|=termios.ICRNL;termios.tcsetattr(0,termios.TCSANOW,raw)
            actual=termios.tcgetattr(0);r.update(lflag=actual[3],iflag=actual[0],lnext=actual[6][termios.VLNEXT][0]);assert r['lnext']==lnext
            assert bool(actual[3]&termios.ICANON)==canonical
            note(folder/(name+'-ready.json'),r);received=bytearray();end=time.monotonic()+22;seen=False
            while len(received)<65536:
                piece=read_piece(end);received.extend(piece);r['chunks'].append(piece.hex());r['input_hex']=received.hex()
                if not seen and b'.' in received:
                    note(folder/(name+'-period.json'),{'hex':received.hex()});seen=True
                if (canonical and piece==b'7\n') or (not canonical and received.endswith(b'\r7')):break
            else:raise AssertionError('unexpectedly long test input')
            note(folder/(name+'-done.json'),r)
        end=time.monotonic()+20
        while not (folder/'release').is_file():
            if time.monotonic()>=end:raise TimeoutError('Windows input restoration')
            time.sleep(.05)
        out['completed']=True
    except BaseException:
        out['error']=traceback.format_exc();raise
    finally:
        os.write(1,CSI+b'?2004;2005;2006l');termios.tcsetattr(0,termios.TCSANOW,original);note(folder/'linux.json',out)


if __name__=='__main__':
    assert sys.platform=='linux' and os.isatty(0) and os.isatty(1) and 'microsoft' in Path('/proc/version').read_text().lower()
    run(Path(sys.argv[1]),int(sys.argv[2]))
