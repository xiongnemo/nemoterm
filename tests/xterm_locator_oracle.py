"""Observe DEC Locator in fresh pinned XTerm windows on a private Xvfb display.

Only authored inputs, XTest events and literal mechanism controls live here.
Every expected protocol reply is captured from the unmodified upstream binary.
No local or shared desktop is used.
"""
import argparse
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys
import tempfile
import time

E = b'\x1b'
C = E+b'['
Q = C+b"'|"
MARKER = b'\x1b[0n'


def read(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, ValueError):
        return {}


def write(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data), encoding='utf-8')
    temporary.replace(path)


def child(report, control):
    import tty
    tty.setraw(0)
    phase, command_id, data = None, None, b''
    deadline = time.monotonic()+25
    write(report, dict(phase=phase, command_id=command_id, hex=''))
    while time.monotonic() < deadline:
        command = read(control)
        if command.get('stop'):
            return
        if command and command.get('id') != command_id:
            if command['phase'] != phase:
                phase, data = command['phase'], b''
            command_id = command['id']
            os.write(1, bytes.fromhex(command['hex']))
        if select.select([0], [], [], .005)[0]:
            chunk = os.read(0, 65536)
            if not chunk:
                return
            data += chunk
        write(report, dict(phase=phase, command_id=command_id, hex=data.hex()))
    raise TimeoutError('Owned reference child lifetime exceeded')


class Display:
    def __init__(self, name):
        self.x = c.CDLL('libX11.so.6')
        self.xt = c.CDLL('libXtst.so.6')
        pointer, window, integer = c.c_void_p, c.c_ulong, c.c_int
        unsigned = c.c_uint
        def bind(lib, name, result, *args):
            f = getattr(lib, name); f.restype = result; f.argtypes = args
        bind(self.x, 'XOpenDisplay', pointer, c.c_char_p)
        bind(self.x, 'XCloseDisplay', integer, pointer)
        bind(self.x, 'XDefaultRootWindow', window, pointer)
        bind(self.x, 'XQueryTree', integer, pointer, window, c.POINTER(window),
             c.POINTER(window), c.POINTER(c.POINTER(window)), c.POINTER(unsigned))
        bind(self.x, 'XGetGeometry', integer, pointer, window, c.POINTER(window),
             c.POINTER(integer), c.POINTER(integer), *([c.POINTER(unsigned)]*4))
        bind(self.x, 'XFree', integer, pointer)
        bind(self.x, 'XWarpPointer', integer, pointer, window, window,
             integer, integer, unsigned, unsigned, integer, integer)
        bind(self.x, 'XSync', integer, pointer, integer)
        bind(self.x, 'XQueryPointer', integer, pointer, window, c.POINTER(window),
             c.POINTER(window), *([c.POINTER(integer)]*4), c.POINTER(unsigned))
        bind(self.x, 'XStringToKeysym', c.c_ulong, c.c_char_p)
        bind(self.x, 'XKeysymToKeycode', c.c_ubyte, pointer, c.c_ulong)
        bind(self.xt, 'XTestFakeButtonEvent', integer, pointer, unsigned, integer, c.c_ulong)
        bind(self.xt, 'XTestFakeKeyEvent', integer, pointer, unsigned, integer, c.c_ulong)
        self.d = self.x.XOpenDisplay(name.encode())
        assert self.d
        self.root = self.x.XDefaultRootWindow(self.d)
        self.window = None

    def windows(self, parent=None, depth=0):
        result = []
        root, actual_parent, count = c.c_ulong(), c.c_ulong(), c.c_uint()
        children = c.POINTER(c.c_ulong)()
        assert self.x.XQueryTree(self.d, parent or self.root, c.byref(root),
                                c.byref(actual_parent), c.byref(children), c.byref(count))
        ids = list(children[:count.value])
        if children:
            self.x.XFree(children)
        for child in ids:
            x, y = c.c_int(), c.c_int()
            w, h, border, bits = (c.c_uint() for _ in range(4))
            assert self.x.XGetGeometry(self.d, child, c.byref(root), c.byref(x), c.byref(y),
                                      c.byref(w), c.byref(h), c.byref(border), c.byref(bits))
            result.append(dict(window=child, width=w.value, height=h.value,
                               x=x.value, y=y.value, border=border.value, depth=depth))
            result += self.windows(child, depth+1)
        return result

    def pointer(self):
        root, child = c.c_ulong(), c.c_ulong()
        rx, ry, x, y = (c.c_int() for _ in range(4))
        mask = c.c_uint()
        present = self.x.XQueryPointer(self.d, self.window, c.byref(root), c.byref(child),
            c.byref(rx), c.byref(ry), c.byref(x), c.byref(y), c.byref(mask))
        return dict(present=bool(present), x=x.value, y=y.value, mask=mask.value)

    def action(self, action, cell):
        kind, *values = action
        if kind == 'move':
            col, row = values
            x, y = 2+(col-1)*cell[0]+cell[0]//2, 2+(row-1)*cell[1]+cell[1]//2
            self.x.XWarpPointer(self.d, 0, self.window, 0, 0, 0, 0, x, y)
        elif kind == 'pixel':
            self.x.XWarpPointer(self.d, 0, self.window, 0, 0, 0, 0, *values)
        elif kind == 'button':
            assert self.xt.XTestFakeButtonEvent(self.d, values[0], values[1], 0)
        elif kind == 'key':
            code = self.x.XKeysymToKeycode(self.d, self.x.XStringToKeysym(values[0].encode()))
            assert code and self.xt.XTestFakeKeyEvent(self.d, code, values[1], 0)
        else:
            raise AssertionError(action)
        self.x.XSync(self.d, False)
        time.sleep(.04)
        return dict(action=action, pointer=self.pointer())

    def close(self):
        self.x.XCloseDisplay(self.d)


def cases():
    result = {}
    def add(name, *steps):
        assert name not in result
        result[name] = steps
    def step(wire=b'', *actions):
        return dict(sequence_hex=wire.hex(), actions=actions)
    down, up = ('button', 1, 1), ('button', 1, 0)
    add('literal-disabled', step(Q))
    add('literal-cell-request', step(C+b"1;2'z"+Q))
    add('literal-left-events', step(C+b"1;2'z"+C+b"1;3'{"), step(b'', down), step(b'', up))
    add('bound-fourth-button', step(C+b"1;2'z"+C+b"1;3'{"),
        step(b'', ('button',4,1)), step(Q), step(b'', ('button',4,0)), step(Q))
    add('bound-control-left', step(C+b"1;2'z"+C+b"1;3'{"),
        step(b'', ('key','Control_L',1), down, up, ('key','Control_L',0)), step(Q))
    for enable in ('', '0', '1', '2', '3', '65535'):
        for unit in ('', '0', '1', '2', '9'):
            setup = C+(enable+(';' + unit if unit else '')+"'z").encode()
            add('enable-'+(enable or 'default')+'-unit-'+(unit or 'default'),
                step(setup+Q), step(Q), step(C+b"1'|"), step(C+b"2'|"))
    for events in ('', '0', '1', '2', '3', '4', '1;3', '1;2;3', '1;0;3',
                   '3;4', '0;1;3', '9;1;3', '1:3', '1;3;0'):
        add('events-'+(events or 'default'), step(C+b"1'z"+C+events.encode()+b"'{"),
            step(b'', down), step(Q), step(b'', up), step(Q))
    for button in (1, 2, 3, 4, 5):
        add('button-'+str(button), step(C+b"1;2'z"+C+b"1;3'{"),
            step(b'', ('button',button,1)), step(Q),
            step(b'', ('button',button,0)), step(Q))
    add('multiple-buttons', step(C+b"1;2'z"+C+b"1;3'{"),
        step(b'', down), step(b'', ('button',3,1)), step(Q),
        step(b'', up), step(b'', ('button',3,0)), step(Q))
    for events in ('1', '3', '1;3'):
        add('one-shot-'+events, step(C+b"2'z"+C+events.encode()+b"'{"),
            step(b'', down), step(b'', up), step(Q), step(C+b"1'z"+Q))
    for value in ('', '0;0;0;0', '5;10;9;15', '9;15;5;10', '1;1;2;2',
                  '1;1;24;80', '1;1;65535;65535', '7;12;7;12'):
        add('filter-'+(value or 'default'), step(C+b"1;2'z"+C+value.encode()+b"'w"),
            step(b'', ('move',13,7)), step(b'', ('move',16,10)), step(Q))
    for follow in (Q, C+b"1;3'{", C+b"0'{", C+b"1'z", C+b"0'z"):
        add('filter-follow-'+follow.hex(), step(C+b"1;2'z"+C+b"1;3'{"+C+b"5;10;9;15'w"),
            step(follow), step(b'', down, up), step(Q))
    for unit in (1, 2):
        for point in ((0,0), (-30,-30), (900,600), (3,3)):
            add('bounds-'+str(unit)+'-'+str(point), step(C+f"1;{unit}'z".encode()),
                step(b'', ('pixel',*point)), step(Q), step(C+b"'w"),
                step(b'', ('move',12,7)), step(Q))
    for modifier in ('Shift_L','Control_L','Alt_L'):
        add('modifier-'+modifier, step(C+b"1;2'z"+C+b"1;3'{"),
            # Shift can start local selection, which suspends XTerm PTY reads.
            # Finish that owned gesture before requesting the trailing barrier.
            step(b'', ('key',modifier,1), down, up, ('key',modifier,0)), step(Q))
    for reset in (E+b'c', C+b'!p', C+b'63;1"p', C+b'?1049h', C+b'?1049h'+C+b'?1049l'):
        add('lifetime-'+reset.hex(), step(C+b"1;2'z"+C+b"1;3'{"),
            step(reset+Q), step(b'', down, up), step(Q))
    for level in (1,2,3,4,5):
        add('dec-level-'+str(level), step(C+f'{60+level};1"p'.encode()+C+b"1;2'z"+Q),
            step(C+b'?55n'+C+b'?56n'), step(C+b"1;3'{", down), step(b'', up))
    for mode in (9,1000,1001,1002,1003):
        add('xterm-overrides-'+str(mode), step(C+b"1;2'z"+C+b"1;3'{"+C+f'?{mode}h'.encode()+Q),
            step(C+f'?{mode}l'.encode()+Q), step(C+b"1'z"+Q))
        add('locator-overrides-'+str(mode), step(C+f'?{mode}h'.encode()+C+b"1;2'z"+Q),
            step(C+f'?{mode}$p'.encode()), step(C+f'?{mode}l'.encode()+Q))
    return result


def capture_case(executable, display_name, name, steps, directory):
    # Evidence must also extract on Windows; parameter colons are not valid
    # filenames there, and replacing punctuation alone would collide.
    safe_name = re.sub(r'[^A-Za-z0-9_.-]+', '_', name)
    folder = directory/(safe_name+'-'+hashlib.sha256(name.encode()).hexdigest()[:8])
    folder.mkdir()
    report, control = folder/'child.json', folder/'control.json'
    display = Display(display_name)
    resource_args = []
    if name.startswith('bound-'):
        # Default XTerm maps wheel-down presses to scrolling and Ctrl+button
        # to menus before its locator dispatcher. Exercise that same unmodified
        # dispatcher with explicit user bindings as a separate named profile.
        bindings = ('XTerm*VT100.translations: #override\\n'
                    '<Btn4Down>: select-start()\\n<Btn4Up>: select-end(SELECT,CUT_BUFFER0)\\n'
                    'Ctrl<Btn1Down>: select-start()\\nCtrl<Btn1Up>: select-end(SELECT,CUT_BUFFER0)')
        resource_args = ['-xrm', bindings]
    terminal = subprocess.Popen([executable, '-geometry','80x24+10+10','-b','2','-bw','0',
        '+sb','-fn','fixed','-ti','vt525','-xrm','XTerm*locale:false','-xrm','XTerm*wideChars:true',
        *resource_args,'-e',sys.executable,str(Path(__file__).resolve()),'--child',str(report),str(control)],
        env=dict(os.environ,DISPLAY=display_name), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    result = dict(name=name, completed=False, steps=[], extra_resource_args=resource_args)
    counter = 0
    active_phase, expected_markers = None, 0
    def command(phase, wire):
        nonlocal counter, active_phase, expected_markers
        counter += 1
        if active_phase != phase:
            active_phase, expected_markers = phase, 0
        expected_markers += 1
        write(control, dict(id=counter,phase=phase,hex=wire.hex()))
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            value = read(report)
            data = bytes.fromhex(value.get('hex',''))
            if (value.get('command_id') == counter and data.endswith(MARKER)
                    and data.count(MARKER) == expected_markers):
                return data
            if terminal.poll() is not None:
                raise AssertionError(('XTerm exited',terminal.returncode,terminal.stderr.read().decode(errors='replace')))
            time.sleep(.005)
        raise AssertionError((name, phase, counter, read(report)))
    try:
        deadline=time.monotonic()+5
        while not report.exists() and time.monotonic()<deadline:
            time.sleep(.01)
        assert report.exists()
        dimensions = command('geometry', C+b'16t'+C+b'5n')
        match = re.fullmatch(rb'\x1b\[6;(\d+);(\d+)t\x1b\[0n',dimensions)
        assert match, dimensions
        cell = [int(match[2]),int(match[1])]
        windows = display.windows()
        candidates=[w for w in windows if w['width']==80*cell[0]+4 and w['height']==24*cell[1]+4]
        assert candidates, (cell,windows)
        display.window=max(candidates,key=lambda w:w['depth'])['window']
        result.update(cell_pixels=cell, window_tree=windows, viewport_window=display.window,
                      initial_pointer=display.action(('move',12,7),cell))
        for index, spec in enumerate(steps):
            phase='step-'+str(index)
            wire=bytes.fromhex(spec['sequence_hex'])
            prefix=command(phase,wire+C+b'5n')
            actions=[display.action(a,cell) for a in spec['actions']]
            full=command(phase,C+b'5n')
            assert full.startswith(prefix) and full.endswith(MARKER)
            # Leave time for a queued X event to reach the child, then require
            # the same complete frame. A late event fails capture, never merges
            # silently into the next reference observation.
            time.sleep(.06)
            assert bytes.fromhex(read(report)['hex'])==full,(name,phase,'late event')
            reply=prefix[:-len(MARKER)]+full[len(prefix):-len(MARKER)]
            result['steps'].append(dict(**spec,reply_hex=reply.hex(),wire_with_barriers_hex=full.hex(),
                                        actions_observed=actions,pointer=display.pointer()))
        result['completed']=True
    finally:
        # Release only synthetic state on this private display, even on failure.
        for button in range(1,6):
            display.xt.XTestFakeButtonEvent(display.d,button,0,0)
        for key in ('Shift_L','Control_L','Alt_L'):
            code=display.x.XKeysymToKeycode(display.d,display.x.XStringToKeysym(key.encode()))
            display.xt.XTestFakeKeyEvent(display.d,code,0,0)
        display.x.XSync(display.d,False)
        write(control,dict(stop=True))
        try:
            terminal.wait(timeout=3)
        except subprocess.TimeoutExpired:
            terminal.terminate();terminal.wait(timeout=3)
        result['exit_code']=terminal.returncode
        result['stderr']=terminal.stderr.read().decode('utf-8',errors='replace')
        display.close()
        write(folder/'observed.json',result)
    return result


def main():
    if len(sys.argv)>1 and sys.argv[1]=='--child':
        return child(*map(Path,sys.argv[2:4]))
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output);folder=output.with_suffix('');folder.mkdir()
    r,w=os.pipe()
    xvfb=subprocess.Popen(['Xvfb','-displayfd',str(w),'-screen','0','1024x768x24','-nolisten','tcp'],
                          pass_fds=[w],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    os.close(w);display=':'+os.read(r,100).decode().strip();os.close(r)
    result=dict(completed=False,version=subprocess.check_output([args.xterm,'-version'],text=True).strip(),
                executable_sha256=hashlib.sha256(Path(args.xterm).read_bytes()).hexdigest(),
                fixture_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),cases={})
    try:
        for name,steps in cases().items():
            observed=capture_case(args.xterm,display,name,steps,folder)
            result['cases'][name]=observed
            write(output,result)
            print(name, [s['reply_hex'] for s in observed['steps']],flush=True)
        controls={
            'literal-disabled':[b'\x1b[0&w'],
            'literal-cell-request':[b'\x1b[1;0;7;12&w'],
            'literal-left-events':[b'',b'\x1b[2;4;7;12&w',b'\x1b[3;0;7;12&w'],
            'bound-fourth-button':[b'',b'\x1b[8;8;7;12&w',b'\x1b[1;8;7;12&w',
                                   b'\x1b[9;0;7;12&w',b'\x1b[1;0;7;12&w'],
            'bound-control-left':[b'',b'\x1b[2;4;7;12&w\x1b[3;0;7;12&w',b'\x1b[1;0;7;12&w'],
        }
        for name,expected in controls.items():
            assert [bytes.fromhex(s['reply_hex']) for s in result['cases'][name]['steps']]==expected,name
        result['literal_controls']=list(controls)
        result['completed']=True
    finally:
        write(output,result)
        xvfb.terminate();xvfb.wait(timeout=5)


if __name__=='__main__':
    main()
