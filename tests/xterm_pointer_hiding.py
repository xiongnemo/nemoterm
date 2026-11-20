"""Observe the actual X11 cursor before a key, after delivery and after pointer motion."""
import argparse, ctypes as c, hashlib, json, os, re, subprocess, sys, time
from pathlib import Path
from xterm_pointer_colour_oracle import Cursor
from xterm_locator_oracle import Display, read, write
from xterm_state_oracle import child
from pointer_hiding_cases import cases


def collect(exe,out,profile):
    folder=out/str(profile); folder.mkdir(); ctrl=folder/'control.json'; report=folder/'child.json'
    d=Display(os.environ['DISPLAY']); fix=c.CDLL('libXfixes.so.3');fix.XFixesGetCursorImage.argtypes=[c.c_void_p];fix.XFixesGetCursorImage.restype=c.POINTER(Cursor)
    d.x.XSetInputFocus.argtypes=[c.c_void_p,c.c_ulong,c.c_int,c.c_ulong]
    def sample():
        ptr=fix.XFixesGetCursorImage(d.d);assert ptr
        try:
            v=ptr.contents;assert 0<v.width*v.height<=512*512
            pixels=b''.join((p&0xffffffff).to_bytes(4,'big') for p in v.pixels[:v.width*v.height]); digest=hashlib.sha256(pixels).hexdigest();f=folder/(digest+'.argb');
            if not f.exists():f.write_bytes(pixels)
            return dict(width=v.width,height=v.height,hotspot=[v.xhot,v.yhot],visible=any(pixels[::4]),sha256=digest)
        finally:d.x.XFree(ptr)
    args=[str(exe),'-geometry','80x24+10+10','-b','2','-bw','0','+sb','-fn','fixed','-ti','vt520','-xrm',f'XTerm*pointerMode: {profile}','-e',sys.executable,str(Path(__file__).resolve()),'--child',str(report),str(ctrl)]
    proc=subprocess.Popen(args);obs={'executable_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'profile':profile,'rows':[],'completed':False}
    def receive(name,ending):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            v=read(report)
            if v.get('phase')==name and v.get('hex','').endswith(ending.hex()):return bytes.fromhex(v['hex'])
            assert proc.poll() is None;time.sleep(.01)
        raise TimeoutError((name,ending.hex(),read(report)))
    def emit(name,seq):
        write(ctrl,{'phase':name,'sequence':seq+'\x1b[5n'});return receive(name,b'\x1b[0n')
    try:
        geometry=emit('geometry','\x1b[16t');m=re.fullmatch(rb'\x1b\[6;(\d+);(\d+)t\x1b\[0n',geometry);assert m,geometry
        cell=(int(m[2]),int(m[1]));d.window=max((w for w in d.windows() if (w['width'],w['height'])==(80*cell[0]+4,24*cell[1]+4)),key=lambda w:w['depth'])['window'];d.x.XSetInputFocus(d.d,d.window,1,0);d.x.XSync(d.d,False)
        for name,seq,want_hidden in cases(profile!=0):
            d.action(('move',7,5),cell);assert emit(name,seq)==b'\x1b[0n';before=sample()
            d.action(('key','a',True),cell);d.action(('key','a',False),cell);wire=receive(name,b'\x1b[0na');after=sample()
            d.action(('move',8,5),cell);moved=sample();obs['rows'].append(dict(name=name,wire=seq.encode().hex(),received=wire.hex(),before=before,after=after,moved=moved,expected_hidden=want_hidden));write(folder/'observed.json',obs)
        write(ctrl,{'stop':True});assert proc.wait(timeout=6)==0;obs['completed']=True
    finally:
        if proc.poll() is None:
            write(ctrl,{'stop':True})
            try:proc.wait(timeout=4)
            except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=4)
        obs['exit_code']=proc.returncode;write(folder/'observed.json',obs);d.close()
    return [r['name'] for r in obs['rows'] if not r['before']['visible'] or r['after']['visible']==r['expected_hidden'] or not r['moved']['visible']]

if __name__=='__main__':
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    if sys.argv[1:2]==['--child']:child(*map(Path,sys.argv[2:4]))
    else:
        parser=argparse.ArgumentParser();parser.add_argument('exe',type=Path);parser.add_argument('out',type=Path);a=parser.parse_args();a.out.mkdir(parents=True);bad={i:collect(a.exe,a.out,i) for i in (0,2)};assert not any(bad.values()),bad
