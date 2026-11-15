"""Observe xterm resources 3/6/7 and XKB key identities on a private server."""
import argparse
import ctypes as c
import hashlib
import os
from pathlib import Path
import subprocess

import xterm_udk_oracle as harness
from xterm_locator_oracle import Display, write

C = b'\x1b['
RESOURCES = ['-xrm', 'XTerm*VT100.translations: #replace\\n<KeyPress>: insert-seven-bit()',
             '-xrm', 'XTerm*backarrowKey: false']


class ObservedDisplay(Display):
    def __init__(self, name):
        super().__init__(name)
        self.x.XkbLookupKeySym.argtypes = [c.c_void_p,c.c_ubyte,c.c_uint,
                                         c.POINTER(c.c_uint),c.POINTER(c.c_ulong)]
        self.x.XkbLookupKeySym.restype = c.c_int
        self.x.XkbLockModifiers.argtypes = [c.c_void_p,c.c_uint,c.c_uint,c.c_uint]
        self.x.XkbLockModifiers.restype = c.c_int

    def action(self, action, cell):
        observation = {}
        if action[0] == 'key':
            keycode = self.x.XKeysymToKeycode(self.d,self.x.XStringToKeysym(action[1].encode()))
            state = self.pointer()['mask']
            consumed, symbol = c.c_uint(), c.c_ulong()
            assert self.x.XkbLookupKeySym(self.d,keycode,state,c.byref(consumed),c.byref(symbol))
            observation = dict(keycode=keycode,state_before=state,keysym=symbol.value,
                               consumed_modifiers=consumed.value)
        result = super().action(action,cell)
        result.update(observation)
        return result


def prepare_keyboard(display, names):
    # Preserve the existing helper's missing-function-key controls, then add
    # only requested symbols absent from this private server's keyboard map.
    original = harness.prepare_keyboard(display)
    x,d = display.x,display.d
    low,high,width = c.c_int(),c.c_int(),c.c_int()
    x.XDisplayKeycodes(d,c.byref(low),c.byref(high))
    values = x.XGetKeyboardMapping(d,low.value,high.value-low.value+1,c.byref(width))
    assert values
    before = {code:list(values[(code-low.value)*width.value:(code-low.value+1)*width.value])
              for code in range(low.value,high.value+1)}
    x.XFree(values)
    available = [code for code,symbols in before.items() if not any(symbols)]
    added = {}
    for name in sorted(names):
        symbol = x.XStringToKeysym(name.encode())
        assert symbol,name
        if any(symbol in symbols for symbols in before.values()):continue
        assert available,name
        code = available.pop()
        mapping = (c.c_ulong*width.value)(symbol)
        x.XChangeKeyboardMapping(d,code,width.value,mapping,1)
        added[name] = dict(keycode=code,keysym=symbol)
    x.XSync(d,False)
    return dict(original=original,added=added)


def cases():
    result = {}
    modifiers = [tuple(name for bit,name in ((1,'Shift_L'),(2,'Alt_L'),(4,'Control_L'))
                       if mask & bit) for mask in range(8)]
    def add(name, sequence, key, masks=(0,1,4,6), locks=0):
        result[name] = dict(profile='default',resources=RESOURCES,locks=locks,steps=[
            dict(**harness.step(sequence,key,modifiers[mask]),requested_key=key,modifiers=mask)
            for mask in masks])
    add('control-escape', b'', 'Escape', (0,))
    add('control-keypad-enter', b'', 'KP_Enter', (0,))
    add('control-shift', C+b'?6m', 'Shift_L', (0,))
    keypad = ('KP_0','KP_1','KP_5','KP_9','KP_Decimal','KP_Add','KP_Subtract',
              'KP_Multiply','KP_Divide','KP_Enter','KP_Separator','KP_Equal','KP_Tab','KP_Space')
    for key in keypad:
        for fmt in (0,1):
            add(f'keypad-{key}-format{fmt}',C+b'>3;4m'+C+f'>3;{fmt}f'.encode(),key)
        if key in ('KP_1','KP_Decimal'):
            add(f'keypad-{key}-numlock',C+b'>3;4m',key,locks=16)
            add(f'keypad-{key}-application',C+b'>3;4m'+b'\x1b=',key)
    for key in ('Escape','Tab','Return','BackSpace','Pause','Scroll_Lock'):
        for fmt in (0,1):
            add(f'special-{key}-format{fmt}',C+b'>7;4m'+C+f'>7;{fmt}f'.encode(),key,range(8))
    for key in ('Shift_L','Shift_R','Control_L','Control_R','Alt_L','Alt_R',
                'Super_L','Super_R','Caps_Lock','Num_Lock'):
        for fmt in (0,1):
            add(f'modifier-{key}-format{fmt}',C+b'>6;4m'+C+f'>6;{fmt}f'.encode(),key,(0,))
    for key in ('Shift_L','Control_L','Alt_L','Super_L'):
        add('modifier-chord-'+key,C+b'>6;4m',key,
            {'Shift_L':(2,6),'Control_L':(1,3),'Alt_L':(1,5),'Super_L':(5,7)}[key])
    for resource,key in ((3,'KP_1'),(6,'Shift_L'),(7,'Escape')):
        for level in (0,1,2,3,'disabled'):
            sequence = C+(f'>{resource}n' if level=='disabled' else f'>{resource};{level}m').encode()
            add(f'level-resource{resource}-{level}',sequence+C+f'?{resource}m'.encode(),key,(0,4))
        for reset in ('ris','soft','one','all','alternate'):
            sequence = C+f'>{resource};4:5m'.encode()+C+f'>{resource};1f'.encode()
            sequence += {'ris':b'\x1bc','soft':C+b'!p','one':C+f'>{resource}m'.encode(),
                         'all':C+b'>m'+C+b'>f','alternate':C+b'?1049h'+C+b'?1049l'}[reset]
            sequence += C+f'?{resource}m'.encode()+C+f'>{resource}g'.encode()+b'\x1bP$q'+f'>{resource}m'.encode()+b'\x1b\\'
            result[f'state-resource{resource}-{reset}'] = dict(profile='default',resources=RESOURCES,
                locks=0,steps=[dict(**harness.step(sequence),requested_key=None,modifiers=0)])
    # Explicitly record classification at the function/special-key boundary.
    for key in ('Print','Menu','Help'):
        for resource in (2,7):
            add(f'classification-{key}-resource{resource}',C+f'>{resource};4m'.encode(),key,(0,4))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output);folder=output.with_suffix('');folder.mkdir(exist_ok=False)
    r,w=os.pipe()
    xvfb=subprocess.Popen(['Xvfb','-displayfd',str(w),'-screen','0','1024x768x24','-nolisten','tcp'],
                          pass_fds=[w],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    os.close(w);display=':'+os.read(r,100).decode().strip();os.close(r)
    owner=ObservedDisplay(display)
    harness.Display=ObservedDisplay
    subprocess.run(['setxkbmap','-display',display,'-option','','-option','srvrkeys:none'],check=True)
    specs=cases()
    names={action[1] for spec in specs.values() for step in spec['steps'] for action in step['actions']}
    result=dict(completed=False,version=subprocess.check_output([args.xterm,'-version'],text=True).strip(),
        executable_sha256=hashlib.sha256(Path(args.xterm).read_bytes()).hexdigest(),
        fixtures={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                  [Path(__file__),Path(__file__).with_name('xterm_udk_oracle.py'),
                   Path(__file__).with_name('xterm_locator_oracle.py')]},cases={})
    try:
        result['private_keyboard']=prepare_keyboard(owner,names)
        controls={'control-escape':[b'\x1b'],'control-keypad-enter':[b'\r'],
                  'control-shift':[b'\x1b[>6;0m']}
        for name,spec in specs.items():
            assert owner.x.XkbLockModifiers(owner.d,256,18,spec['locks'])
            owner.x.XSync(owner.d,False)
            observed=harness.capture_case(args.xterm,display,name,spec,folder)
            observed['requested_locks']=spec['locks']
            result['cases'][name]=observed;write(output,result)
            assert observed['completed'] and observed['exit_code']==0
            if name in controls:
                assert [bytes.fromhex(s['reply_hex']) for s in observed['steps']]==controls[name],name
            print(name,len(observed['steps']),flush=True)
        result['completed']=True
    finally:
        write(output,result);owner.close();xvfb.terminate();xvfb.wait(timeout=5)


if __name__=='__main__':main()
