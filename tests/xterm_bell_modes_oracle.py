"""Observe xterm bell modes, urgency hints and stacking on a private display."""
import argparse
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from xterm_locator_oracle import Display, child, read, write, MARKER

C = b'\x1b['
QUERY = C+b'?1042$p'+C+b'?1043$p'

def step(sequence=b'', focus=None, cover=False):
    return dict(sequence_hex=sequence.hex(), focus=focus, cover=cover)

def cases():
    result = {}
    for urgent,raise_ in [(False,False),(True,False),(False,True),(True,True)]:
        profile = f'{int(urgent)}{int(raise_)}'
        def add(name,*steps):
            result[profile+'-'+name] = dict(urgent=urgent,raise_=raise_,steps=steps)
        add('initial',step(QUERY))
        for mode in (1042,1043):
            prefix = C+f'?{mode}'.encode()
            add(f'{mode}-toggle',step(prefix+b'h'+QUERY),step(prefix+b'l'+QUERY))
            add(f'{mode}-save-on',step(prefix+b'h'+prefix+b's'+prefix+b'l'+QUERY),step(prefix+b'r'+QUERY))
            add(f'{mode}-save-off',step(prefix+b'l'+prefix+b's'+prefix+b'h'+QUERY),step(prefix+b'r'+QUERY))
            add(f'{mode}-unsaved',step(prefix+b'h'+prefix+b'r'+QUERY))
        for name,reset in [('ris',b'\x1bc'),('soft',C+b'!p'),('level',C+b'63;1"p'),
                           ('alt',C+b'?1049h'),('alt-roundtrip',C+b'?1049h'+C+b'?1049l')]:
            add('lifetime-'+name,step(C+b'?1042;1043h'+QUERY),step(reset+QUERY))
            add('saved-'+name,step(C+b'?1042;1043h'+C+b'?1042;1043s'+C+b'?1042;1043l'),
                step(reset+C+b'?1042;1043r'+QUERY))
        add('physical-initial',step(b'\x07'+QUERY,'other',True))
        add('physical-on',step(C+b'?1042;1043h'+b'\x07'+QUERY,'other',True),step(QUERY,'term'))
        add('physical-off',step(C+b'?1042;1043l'+b'\x07'+QUERY,'other',True))
        add('urgent-only',step(C+b'?1043l'+C+b'?1042h'+b'\x07'+QUERY,'other',True),step(QUERY,'term'))
        add('raise-only',step(C+b'?1042l'+C+b'?1043h'+b'\x07'+QUERY,'other',True))
        add('focused-bell',step(C+b'?1042;1043h'+b'\x07'+QUERY,'term',True))
        add('disable-before-focus',step(C+b'?1042h'+b'\x07','other',True),
            step(C+b'?1042l'),step(QUERY,'term'))
        add('osc-terminator',step(C+b'?1042;1043h'+b'\x1b]2;bell-reference\x07'+QUERY,'other',True))
        add('dcs-bel',step(C+b'?1042;1043h'+b'\x1bP$q\x07m\x1b\\'+QUERY,'other',True))
    return result

class Hints(c.Structure):
    _fields_ = [('flags',c.c_long),('input',c.c_int),('initial_state',c.c_int),
                ('icon_pixmap',c.c_ulong),('icon_window',c.c_ulong),('icon_x',c.c_int),
                ('icon_y',c.c_int),('icon_mask',c.c_ulong),('window_group',c.c_ulong)]

def capture(executable,display_name,name,spec,base):
    folder = base/name; folder.mkdir()
    report,control = folder/'child.json',folder/'control.json'
    display = Display(display_name)
    x,d = display.x,display.d
    x.XSetInputFocus.argtypes = [c.c_void_p,c.c_ulong,c.c_int,c.c_ulong]
    x.XGetInputFocus.argtypes = [c.c_void_p,c.POINTER(c.c_ulong),c.POINTER(c.c_int)]
    x.XGetWMHints.argtypes = [c.c_void_p,c.c_ulong]; x.XGetWMHints.restype = c.POINTER(Hints)
    x.XCreateSimpleWindow.argtypes = [c.c_void_p,c.c_ulong,c.c_int,c.c_int,c.c_uint,c.c_uint,c.c_uint,c.c_ulong,c.c_ulong]
    x.XCreateSimpleWindow.restype = c.c_ulong
    for method in ('XMapWindow','XRaiseWindow','XDestroyWindow'):
        getattr(x,method).argtypes = [c.c_void_p,c.c_ulong]
    resources = ['-xrm','XTerm*bellIsUrgent:'+str(spec['urgent']).lower(),
                 '-xrm','XTerm*popOnBell:'+str(spec['raise_']).lower(),
                 '-xrm','XTerm*bellSuppressTime:0']
    terminal = subprocess.Popen([executable,'-geometry','80x24+10+10','-b','2','-bw','0',
        '+sb','-fn','fixed','-ti','vt525','-xrm','XTerm*locale:false',*resources,
        '-e',sys.executable,str(Path(__file__).resolve()),'--child',str(report),str(control)],
        env=dict(os.environ,DISPLAY=display_name),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    result = dict(completed=False,resources=resources,steps=[])
    counter,other = 0,0
    def command(phase,wire):
        nonlocal counter
        counter += 1
        write(control,dict(id=counter,phase=phase,hex=(wire+C+b'5n').hex()))
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            value = read(report); received = bytes.fromhex(value.get('hex',''))
            if value.get('phase') == phase and value.get('command_id') == counter and received.endswith(MARKER):
                time.sleep(.04)
                assert read(report)['hex'] == received.hex(),(name,phase,'late reply')
                return received
            assert terminal.poll() is None,('XTerm exited',terminal.returncode)
            time.sleep(.005)
        raise AssertionError((name,phase,read(report)))
    def state():
        x.XSync(d,False)
        focus,revert = c.c_ulong(),c.c_int()
        x.XGetInputFocus(d,c.byref(focus),c.byref(revert))
        hints = x.XGetWMHints(d,shell)
        assert hints
        try: flags = hints.contents.flags
        finally: x.XFree(hints)
        order = [v['window'] for v in display.windows() if v['depth'] == 0]
        return dict(urgency=bool(flags&256),hint_flags=flags,focus=focus.value,
                    term_focused=focus.value in (shell,viewport),root_stack=order,
                    above_other=order.index(shell)>order.index(other))
    try:
        deadline = time.monotonic()+5
        while not report.exists() and time.monotonic() < deadline: time.sleep(.01)
        assert report.exists()
        geometry = command('geometry',C+b'16t')
        match = re.fullmatch(rb'\x1b\[6;(\d+);(\d+)t\x1b\[0n',geometry); assert match
        cell = [int(match[2]),int(match[1])]
        windows = display.windows()
        same = [v for v in windows if v['width']==80*cell[0]+4 and v['height']==24*cell[1]+4]
        shell = min(same,key=lambda v:v['depth'])['window']
        viewport = max(same,key=lambda v:v['depth'])['window']
        other = x.XCreateSimpleWindow(d,display.root,20,20,400,300,0,0,0)
        assert other; x.XMapWindow(d,other); x.XSync(d,False)
        result.update(shell_window=shell,viewport_window=viewport,other_window=other,cell_pixels=cell,initial_window_tree=windows)
        for i,phase in enumerate(spec['steps']):
            if phase['cover']: x.XRaiseWindow(d,other)
            if phase['focus']: x.XSetInputFocus(d,viewport if phase['focus']=='term' else other,1,0)
            x.XSync(d,False); time.sleep(.06)
            before = state()
            wire = command(str(i),bytes.fromhex(phase['sequence_hex']))
            result['steps'].append(dict(**phase,reply_hex=wire[:-len(MARKER)].hex(),
                wire_with_barrier_hex=wire.hex(),window_before=before,window_after=state()))
        result['completed'] = True
    finally:
        write(control,dict(stop=True))
        try: terminal.wait(timeout=3)
        except subprocess.TimeoutExpired: terminal.terminate();terminal.wait(timeout=3)
        result['exit_code'] = terminal.returncode
        result['stderr'] = terminal.stderr.read().decode('utf-8',errors='replace')
        if other: x.XDestroyWindow(d,other)
        display.close(); write(folder/'observed.json',result)
    return result

def main():
    if len(sys.argv)>1 and sys.argv[1]=='--child': return child(*map(Path,sys.argv[2:4]))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm',required=True); parser.add_argument('--output',required=True)
    args = parser.parse_args(); output = Path(args.output); base = output.with_suffix(''); base.mkdir()
    r,w = os.pipe()
    xvfb = subprocess.Popen(['Xvfb','-displayfd',str(w),'-screen','0','1024x768x24','-nolisten','tcp'],
                            pass_fds=[w],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    os.close(w); display = ':'+os.read(r,100).decode().strip(); os.close(r)
    result = dict(completed=False,version=subprocess.check_output([args.xterm,'-version'],text=True).strip(),
                  executable_sha256=hashlib.sha256(Path(args.xterm).read_bytes()).hexdigest(),
                  fixture_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),cases={})
    try:
        for name,spec in cases().items():
            result['cases'][name] = capture(args.xterm,display,name,spec,base); write(output,result)
            print(name,[s['reply_hex'] for s in result['cases'][name]['steps']],flush=True)
        off = result['cases']['00-physical-off']['steps'][0]['window_after']
        on = result['cases']['00-physical-on']['steps'][0]['window_after']
        focus = result['cases']['00-physical-on']['steps'][1]['window_after']
        assert not off['urgency'] and not off['above_other'] and not off['term_focused']
        assert on['urgency'] and on['above_other'] and not on['term_focused']
        assert not focus['urgency'] and focus['term_focused']
        result['literal_controls'] = ['off-no-attention','on-urgent-raised-no-focus','focus-clears-urgent']
        result['completed'] = True
    finally:
        write(output,result); xvfb.terminate(); xvfb.wait(timeout=5)

if __name__ == '__main__': main()
