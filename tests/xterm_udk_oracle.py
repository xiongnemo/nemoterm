"""Observe DECUDK storage and physical function-key dispatch on private Xvfb.

The upstream parser and keyboard code are unmodified. Payloads and key actions
are authored inputs; output bytes are captured, with only small literal controls.
"""
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

E = b'\x1b'
C = E+b'['
ST = E+b'\\'
STATUS = C+b'?25n'


def dcs(payload, header=b'0;1'):
    return E+b'P'+header+b'|'+payload+ST


def step(sequence=b'', key=None, modifiers=('Shift_L',)):
    actions = []
    if key:
        actions += [('key', m, 1) for m in modifiers]
        actions += [('key', key, 1), ('key', key, 0)]
        actions += [('key', m, 0) for m in reversed(modifiers)]
    return dict(sequence_hex=sequence.hex(), actions=actions)


def cases():
    result = {}
    def add(name, *steps, profile='vt220'):
        assert name not in result
        result[name] = dict(profile=profile, steps=steps)

    add('literal-status', step(STATUS))
    add('literal-definition', step(dcs(b'17/414243'), 'F6'), step(STATUS))
    add('literal-unshifted', step(dcs(b'17/414243'), 'F6', ()))
    add('default-profile', step(dcs(b'17/414243'), 'F6'), profile='default')
    codes = [11,12,13,14,15,17,18,19,20,21,23,24,25,26,28,29,31,32,33,34]
    for index, code in enumerate(codes, 1):
        value = f'K{code}'.encode().hex().encode()
        add(f'function-F{index}', step(dcs(str(code).encode()+b'/'+value), f'F{index}'))
    for header in (b'', b'0', b'1', b'2', b'9', b'65535'):
        add('clear-'+(header.decode() or 'default'),
            step(dcs(b'17/41;18/42'), 'F6'),
            step(dcs(b'17/43', header), 'F6'), step(key='F7'), step(STATUS))
    for lock in (b'', b'0', b'1', b'2', b'9', b'65535'):
        add('lock-'+(lock.decode() or 'default'),
            step(dcs(b'17/41', b'0;'+lock), 'F6'), step(STATUS),
            step(dcs(b'17/42', b'1;1'), 'F6'), step(STATUS))
    payloads = {
        'empty':b'', 'empty-value':b'17/', 'one-nibble':b'17/4',
        'odd-nibbles':b'17/414', 'lowercase':b'17/6a6b',
        'commas':b'17/4,1,4,2', 'spaces':b'17/4 1 4 2', 'junk':b'17/g4!1z42',
        'invalid-only':b'17/xyz', 'empty-first':b';17/42', 'empty-middle':b'17/42;;18/43',
        'duplicate':b'17/42;17/43', 'empty-overwrite':b'17/42;17/',
        'odd-before-next':b'17/4;18/43', 'missing-slash':b'17;18/43',
        'key-zero':b'0/5a;17/42', 'unknown-key':b'99/5a;17/42',
        'key-leading-zeros':b'00017/42', 'key-junk-prefix':b'x17/42;18/43',
        'trailing-junk':b'17/42xxx', 'duplicate-empty-next':b'17/42;18/;17/43',
        'binary':b'17/00017f809bff', 'escape-data':b'17/1b5b33316d',
    }
    for name, payload in payloads.items():
        add('payload-'+name, step(dcs(b'17/41;18/44')), step(dcs(payload,b'1;1'),'F6'),
            step(key='F7'), step(STATUS))
    for header in (b';1',b'1;1;1',b'1:1',b'?1;1',b'>1;1',b'1$'):
        add('header-'+header.hex(),step(dcs(b'17/41')),step(dcs(b'17/42',header),'F6'))
    for ending in (b'\x18',b'\x1a',C+b'0m',b'\x07'):
        add('interrupt-'+ending.hex(),step(dcs(b'17/41')),
            step(E+b'P0;1|17/42'+ending+ST,'F6'),step(STATUS))
    for name, reset in [('ris',E+b'c'),('soft',C+b'!p'),('level',C+b'63;1"p'),
                        ('alt',C+b'?1049h'),('alt-roundtrip',C+b'?1049h'+C+b'?1049l')]:
        add('lifetime-'+name,step(dcs(b'17/41'),'F6'),step(reset,'F6'),step(STATUS))
    for level in range(1,6):
        add('dec-level-'+str(level),step(C+f'{60+level};1"p'.encode()+dcs(b'17/41'),'F6'),step(STATUS))
    for modifiers in ((),('Control_L',),('Alt_L',),('Shift_L','Control_L'),
                      ('Shift_L','Alt_L'),('Shift_L','Control_L','Alt_L')):
        add('modifiers-'+('-'.join(modifiers) or 'none'),
            step(dcs(b'17/41;32/42'),'F6',modifiers),step(STATUS))
    for length in (1,255,256,1024,4096):
        add('length-'+str(length),step(dcs(b'17/'+b'41'*length),'F6'),step(STATUS))
    add('eight-bit-dcs',step(E+b'%@'+b'\x900;1|17/41\x9c','F6'),step(STATUS))
    return result


def prepare_keyboard(display):
    """Add missing function symbols to unused keys on our private Xvfb only.

    Keep this connection open for the capture so Xvfb cannot reset the map
    between cases. New XTerm/observer clients read the completed server map.
    """
    x, d = display.x, display.d
    x.XDisplayKeycodes.argtypes = [c.c_void_p, c.POINTER(c.c_int), c.POINTER(c.c_int)]
    x.XGetKeyboardMapping.argtypes = [c.c_void_p, c.c_ubyte, c.c_int, c.POINTER(c.c_int)]
    x.XGetKeyboardMapping.restype = c.POINTER(c.c_ulong)
    x.XChangeKeyboardMapping.argtypes = [c.c_void_p, c.c_int, c.c_int,
                                        c.POINTER(c.c_ulong), c.c_int]
    low, high, width = c.c_int(), c.c_int(), c.c_int()
    x.XDisplayKeycodes(d, c.byref(low), c.byref(high))
    def mapping():
        values = x.XGetKeyboardMapping(d, low.value, high.value-low.value+1, c.byref(width))
        assert values
        try:
            return {code: [values[(code-low.value)*width.value+i] for i in range(width.value)]
                    for code in range(low.value, high.value+1)}
        finally:
            x.XFree(values)
    before = mapping()
    available = [code for code, symbols in before.items() if not any(symbols)]
    added = {}
    for name in [f'F{i}' for i in range(1,21)]:
        symbol = x.XStringToKeysym(name.encode())
        assert symbol
        if not any(symbol in symbols for symbols in before.values()):
            assert available, 'No unused private-display keycode for '+name
            code = available.pop()
            values = (c.c_ulong*width.value)(symbol)
            x.XChangeKeyboardMapping(d, code, width.value, values, 1)
            added[name] = dict(keycode=code, keysym=symbol)
    x.XSync(d, False)
    after = mapping()
    for item in added.values():
        assert item['keysym'] in after[item['keycode']]
    return dict(before=before, after=after, added=added)


def capture_case(executable, display_name, name, spec, base):
    folder = base/(re.sub(r'[^A-Za-z0-9_-]','_',name)+'-'+hashlib.sha256(name.encode()).hexdigest()[:8])
    folder.mkdir()
    report, control = folder/'child.json', folder/'control.json'
    display = Display(display_name)
    resource_args = ['-xrm','XTerm*keyboardType:'+spec['profile'], '-xrm','XTerm*ctrlFKeys:12']
    resource_args += spec.get('resources', [])
    terminal = subprocess.Popen([executable,'-geometry','80x24+10+10','-b','2','-bw','0',
        '+sb','-fn','fixed','-ti','vt525','-xrm','XTerm*locale:false','-xrm','XTerm*wideChars:true',
        *resource_args,'-e',sys.executable,str(Path(__file__).resolve()),'--child',str(report),str(control)],
        env=dict(os.environ,DISPLAY=display_name),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    result = dict(name=name,profile=spec['profile'],resources=resource_args,completed=False,steps=[])
    counter = 0
    active_phase, markers = None, 0
    def command(phase, wire):
        nonlocal counter, active_phase, markers
        counter += 1
        if active_phase != phase: active_phase,markers = phase,0
        markers += 1
        write(control,dict(id=counter,phase=phase,hex=wire.hex()))
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            value = read(report); data = bytes.fromhex(value.get('hex',''))
            if value.get('phase') == phase and value.get('command_id') == counter and data.count(MARKER) == markers:
                return data
            assert terminal.poll() is None, ('XTerm exited',terminal.returncode)
            time.sleep(.005)
        raise AssertionError((name,phase,counter,read(report)))
    try:
        deadline = time.monotonic()+5
        while not report.exists() and time.monotonic() < deadline: time.sleep(.01)
        assert report.exists()
        dimensions = command('geometry',C+b'16t'+C+b'5n')
        match = re.fullmatch(rb'\x1b\[6;(\d+);(\d+)t\x1b\[0n',dimensions)
        assert match,dimensions
        cell = [int(match[2]),int(match[1])]
        windows = display.windows()
        candidates = [w for w in windows if w['width']==80*cell[0]+4 and w['height']==24*cell[1]+4]
        assert candidates
        display.window = max(candidates,key=lambda w:w['depth'])['window']
        display.action(('move',12,7),cell)
        display.x.XSetInputFocus.argtypes = [c.c_void_p,c.c_ulong,c.c_int,c.c_ulong]
        display.x.XSetInputFocus(display.d,display.window,1,0)
        display.x.XSync(display.d,False)
        result.update(cell_pixels=cell,viewport_window=display.window,window_tree=windows)
        result['keycodes'] = {key: display.x.XKeysymToKeycode(
            display.d, display.x.XStringToKeysym(key.encode()))
            for key in ['Shift_L','Control_L','Alt_L']+[f'F{i}' for i in range(1,21)]}
        assert all(result['keycodes'].values()), result['keycodes']
        for index, phase_spec in enumerate(spec['steps']):
            phase = 'step-'+str(index)
            prefix = command(phase,bytes.fromhex(phase_spec['sequence_hex'])+C+b'5n')
            actions = [display.action(a,cell) for a in phase_spec['actions']]
            full = command(phase,C+b'5n')
            assert full.startswith(prefix) and full.endswith(MARKER)
            time.sleep(.06)
            assert bytes.fromhex(read(report)['hex']) == full,(name,phase,'late input')
            reply = prefix[:-len(MARKER)]+full[len(prefix):-len(MARKER)]
            result['steps'].append(dict(**phase_spec,reply_hex=reply.hex(),wire_with_barriers_hex=full.hex(),
                                        actions_observed=actions))
        result['completed'] = True
    finally:
        for key in ['Shift_L','Control_L','Alt_L']+[f'F{i}' for i in range(1,21)]:
            code = display.x.XKeysymToKeycode(display.d,display.x.XStringToKeysym(key.encode()))
            if code: display.xt.XTestFakeKeyEvent(display.d,code,0,0)
        display.x.XSync(display.d,False)
        write(control,dict(stop=True))
        try: terminal.wait(timeout=3)
        except subprocess.TimeoutExpired: terminal.terminate();terminal.wait(timeout=3)
        result['exit_code'] = terminal.returncode
        result['stderr'] = terminal.stderr.read().decode('utf-8',errors='replace')
        display.close()
        write(folder/'observed.json',result)
    return result


def main():
    if len(sys.argv)>1 and sys.argv[1]=='--child': return child(*map(Path,sys.argv[2:4]))
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output);folder=output.with_suffix('');folder.mkdir()
    r,w=os.pipe()
    xvfb=subprocess.Popen(['Xvfb','-displayfd',str(w),'-screen','0','1024x768x24','-nolisten','tcp'],
                          pass_fds=[w],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    os.close(w);display=':'+os.read(r,100).decode().strip();os.close(r)
    owner = Display(display)
    result=dict(completed=False,version=subprocess.check_output([args.xterm,'-version'],text=True).strip(),
                executable_sha256=hashlib.sha256(Path(args.xterm).read_bytes()).hexdigest(),
                fixture_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                shared_harness_sha256=hashlib.sha256(Path(__file__).with_name('xterm_locator_oracle.py').read_bytes()).hexdigest(),cases={})
    try:
        result['private_keyboard'] = prepare_keyboard(owner)
        for name,spec in cases().items():
            observed=capture_case(args.xterm,display,name,spec,folder)
            result['cases'][name]=observed;write(output,result)
            print(name,[len(bytes.fromhex(s['reply_hex'])) for s in observed['steps']],flush=True)
        controls={'literal-status':[b'\x1b[?20n'],'literal-definition':[b'ABC',b'\x1b[?20n'],
                  'literal-unshifted':[b'\x1b[17~']}
        for name,expected in controls.items():
            assert [bytes.fromhex(s['reply_hex']) for s in result['cases'][name]['steps']]==expected,name
        result['literal_controls']=list(controls);result['completed']=True
    finally:
        write(output,result);owner.close();xvfb.terminate();xvfb.wait(timeout=5)


if __name__=='__main__': main()
