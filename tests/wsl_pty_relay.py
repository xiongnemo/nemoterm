"""Exercise the exact Linux PTY relay on hosted Ubuntu and via redirected WSL1."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import threading
import traceback
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REL = 'build/wsl-relay/relay'
ARG = 'literal space ; $(not-a-command) 中文'
BULK = bytes(range(256)) * 1024
ACK = b'RELAY-PEER-READY\n'
REF_DIGEST = '3d06c7eec267dc31f6fc8c52e2fc2f0b85de3cb932f4bccca10ec31467c044c1'
digest = lambda b: hashlib.sha256(b).hexdigest()


def exact(stream, n):
    result = bytearray()
    while len(result) != n:
        chunk = stream.read(n-len(result))
        if not chunk: raise EOFError(f'expected {n} bytes; got {len(result)}')
        result.extend(chunk)
    return bytes(result)


def samples():
    archive = ROOT/'testdata/upstream/xterm412-paste-quote.zip'
    assert digest(archive.read_bytes()) == REF_DIGEST
    with zipfile.ZipFile(archive) as z:
        for profile in ('default', 'custom'):
            doc = json.loads(z.read('paste-quote/'+profile+'.json'))
            for case in ('quote','restore-lf'):
                yield profile+'/'+case, bytes.fromhex(doc['cases'][case]['paste_hex'])
    yield 'all-bytes', bytes(range(256))


def writeall(fd, data):
    view = memoryview(data)
    while view: view = view[os.write(fd,view):]


def peer(mode, arg):
    import signal, termios, time, tty
    assert arg==ARG and os.environ['TERM']=='xterm' and all(os.isatty(i) for i in (0,1,2))
    assert os.tcgetpgrp(0)==os.getpgrp()==os.getsid(0)
    tty.setraw(0); size=lambda:tuple(os.get_terminal_size(0))
    assert size()==(160,48)
    signals=[]; signal.signal(signal.SIGWINCH,lambda *_: signals.append(size()))
    if mode=='hold': signal.signal(signal.SIGHUP,signal.SIG_IGN)
    writeall(1,ACK)
    if mode=='geometry':
        import fcntl
        def report_size():
            raw=fcntl.ioctl(0,termios.TIOCGWINSZ,bytes(8))
            writeall(1,struct.pack('>HHHH',*struct.unpack('=HHHH',raw)))
        report_size()
        for _ in range(4):
            assert exact(sys.stdin.buffer,1)==b'?';report_size()
        return 37
    if mode=='hold':
        while True: signal.pause()
    if mode=='partial':
        assert os.read(0,1)==b'!';writeall(1,b'Q');return 0
    for _,b in samples():
        actual=exact(sys.stdin.buffer,len(b));writeall(1,actual)
    for expected in ((87,31),(131,45)):
        assert exact(sys.stdin.buffer,1)==b'?' and size()==expected
        deadline=time.monotonic()+2
        while expected not in signals and time.monotonic()<deadline:time.sleep(.01)
        assert expected in signals; writeall(1,struct.pack('>HH',*size()))
    # Fill output before reading the large input. The two directions must make
    # progress independently even when both the pipe and the PTY are full.
    writeall(1,BULK[::-1]); writeall(1,exact(sys.stdin.buffer,len(BULK)))
    writeall(2,b'PEER-STDERR\r\n');return 37


def frame(op,b):return struct.pack('>BH',op,len(b))+b


def run(kind, report):
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    windows=kind=='wsl1'; assert windows==(os.name=='nt')
    env=dict(os.environ,TERM='xterm');options={'creationflags':subprocess.CREATE_NO_WINDOW} if windows else {}
    if windows:
        import re
        listing=subprocess.check_output(['wsl.exe','--list','--verbose'],**options).decode('utf-16-le').replace('\x00','')
        assert re.search(r'(?m)^\s*\*?\s*Ubuntu-24\.04\s+\S+\s+1\s*$',listing),listing
        report['distributions']=listing
    prefix=['wsl.exe','--distribution','Ubuntu-24.04','--cd',str(ROOT),'--exec','/usr/bin/env','TERM=xterm'] if windows else []
    cmd=prefix+['./'+REL,'160','48','/usr/bin/python3','tests/wsl_pty_relay.py','--peer']
    out=ROOT/'build/wsl-relay-records';out.mkdir(parents=True,exist_ok=True)
    geometry=sys.argv[2:]==['--geometry']
    names=('geometry','bad-geometry-length','bad-geometry-grid') if geometry else ('duplex','partial-header','unknown-type','oversize','truncated','bad-grid','close-live')
    for name in names:
        rec=report['cases'][name]={'passed':False}; p=None; timer=None
        mode=name if name in ('duplex','geometry') else 'partial' if name=='partial-header' else 'hold'
        try:
            launch=(prefix+['./'+REL,'--pixels','160','48','1280','960','/usr/bin/python3','tests/wsl_pty_relay.py','--peer'] if mode=='geometry' else cmd)
            p=subprocess.Popen(launch+[mode,ARG],cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**options)
            def expire(proc=p,row=rec):
                row['timed_out']=True
                if proc.poll() is None:proc.kill()
            timer=threading.Timer(32,expire);timer.daemon=True;timer.start()
            def send(b):p.stdin.write(b);p.stdin.flush()
            assert exact(p.stdout,len(ACK))==ACK
            if name=='duplex':
                rec['echoes']={}
                for i,(label,b) in enumerate(samples()):
                    packet=frame(1,b)
                    if i%2: send(packet)
                    else:
                        for octet in packet:send(bytes([octet]))
                    observed=exact(p.stdout,len(b));rec['echoes'][label]={'sent_hex':b.hex(),'received_hex':observed.hex()};assert observed==b
                rec['sizes']=[]
                for w,h in ((87,31),(131,45)):
                    send(frame(2,struct.pack('>HH',w,h))+frame(1,b'?'));observed=struct.unpack('>HH',exact(p.stdout,4));rec['sizes'].append(observed);assert observed==(w,h)
                errors=[]
                def send_bulk():
                    try:
                        for at in range(0,len(BULK),16384): send(frame(1,BULK[at:at+16384]))
                    except Exception as e:errors.append(repr(e))
                writer=threading.Thread(target=send_bulk,daemon=True);writer.start()
                a,b=exact(p.stdout,len(BULK)),exact(p.stdout,len(BULK));writer.join(5)
                assert not errors and not writer.is_alive();rec['bulk']={'bytes_each':len(BULK),'output_sha256':digest(a),'echo_sha256':digest(b)};assert a==BULK[::-1] and b==BULK
                assert exact(p.stdout,13)==b'PEER-STDERR\r\n';wanted=37
            elif name=='geometry':
                rec['sizes']=[]
                def measured(expect):
                    rec['sizes'].append(dict(expected=expect,observed=struct.unpack('>HHHH',exact(p.stdout,8))))
                measured((48,160,1280,960))
                for op,(rows,cols,x,y) in [(3,(31,87,696,620)),(3,(31,87,783,651)),(3,(45,131,65535,32768)),(2,(24,80,0,0))]:
                    payload=struct.pack('>HHHH',cols,rows,x,y) if op==3 else struct.pack('>HH',cols,rows)
                    send(frame(op,payload)+frame(1,b'?'));measured((rows,cols,x,y))
                wanted=37
            elif name=='partial-header':
                # Last write includes a following header fragment. It must
                # never prevent already-produced child output from reaching us.
                send(frame(1,b'!')+b'\x01');assert exact(p.stdout,1)==b'Q';wanted=0
            else:
                packet={'unknown-type':b'\x77\0\x01','oversize':b'\x01\x40\x01','truncated':b'\x01\0\x04xx',
                        'bad-grid':frame(2,b'\0\0\0\x18'),'bad-geometry-length':frame(3,bytes(4)),
                        'bad-geometry-grid':frame(3,bytes(8)),'close-live':b''}[name]
                if packet:send(packet)
                if name in ('truncated','close-live'):p.stdin.close()
                wanted=137 if name=='close-live' else 125
            rec['exit']=p.wait(timeout=12);rec['tail']=p.stdout.read().hex();rec['diagnostic']=p.stderr.read().decode('utf-8','replace')
            assert rec['exit']==wanted and not rec['tail'] and not rec.get('timed_out'),rec
            assert bool(rec['diagnostic'])==(wanted==125),rec['diagnostic']
            if name=='geometry': assert all(row['observed']==row['expected'] for row in rec['sizes']),rec['sizes']
            rec['passed']=True
        except Exception: rec['error']=traceback.format_exc()
        finally:
            if timer:timer.cancel()
            if p:
                if not p.stdin.closed:
                    try:p.stdin.close()
                    except BrokenPipeError:pass
                if p.poll() is None:
                    try:p.wait(timeout=3)
                    except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5);rec['forced_cleanup']=True
                if not rec['passed']:
                    rec['cleanup_exit']=p.returncode
                    if 'diagnostic' not in rec:rec['diagnostic']=p.stderr.read().decode('utf-8','replace')
                p.stdout.close();p.stderr.close()
            (out/(kind+('-geometry' if geometry else '')+'.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    assert all(v['passed'] for v in report['cases'].values()),[(k,v.get('error')) for k,v in report['cases'].items() if not v['passed']]


if __name__=='__main__':
    if sys.argv[1]=='--peer':sys.exit(peer(*sys.argv[2:]))
    kind=sys.argv[1];run(kind,dict(host=kind,fixture_sha256=digest(Path(__file__).read_bytes()),reference_sha256=REF_DIGEST,
                                 relay_sha256=digest((ROOT/REL).read_bytes()),commit=os.environ['GITHUB_SHA'],cases={}))
