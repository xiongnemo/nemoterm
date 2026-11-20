"""Compare the reported DECBKM state, kbs and a real BackSpace on XTerm's PTY."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess

import xterm_udk_oracle as harness
from xterm_extended_keys_oracle import ObservedDisplay, prepare_keyboard
from xterm_locator_oracle import write

CSI = b'\x1b['
QUERY = CSI+b'?67$p' + b'\x1bP+q6b6273\x1b\\'


def plans():
    result = {}
    for keyboard in ('default', 'tcap'):
        for initial in (False, True):
            phases = []
            def observe(label, command=b'', modifiers=(), key='BackSpace'):
                phases.append(dict(harness.step(command+QUERY, key, modifiers), label=label))
            observe('startup'); observe('set', CSI+b'?67h'); observe('set-control', modifiers=('Control_L',)); observe('set-shift', modifiers=('Shift_L',))
            observe('reset', CSI+b'?67l'); observe('reset-control', modifiers=('Control_L',)); observe('reset-shift', modifiers=('Shift_L',))
            observe('restore-set', CSI+b'?67h'+CSI+b'?67s'+CSI+b'?67l'+CSI+b'?67r'); observe('restore-reset',CSI+b'?67l'+CSI+b'?67s'+CSI+b'?67h'+CSI+b'?67r')
            observe('soft-after-set',CSI+b'?67h'+CSI+b'!p'); observe('soft-after-reset',CSI+b'?67l'+CSI+b'!p'); observe('hard-after-set',CSI+b'?67h\x1bc'); observe('hard-after-reset',CSI+b'?67l\x1bc')
            observe('alternate',CSI+b'?67h'+CSI+b'?1049h'); observe('main',CSI+b'?1049l'); observe('delete-control',CSI+b'?67h', key='Delete')
            result[f'{keyboard}-'+('bs' if initial else 'del')]=dict(profile=keyboard, steps=phases, resources=['-xrm','XTerm*backarrowKey:'+('true' if initial else 'false'), '-xrm','XTerm*backarrowKeyIsErase:false','-xrm','XTerm*allowTcapOps:true','-xrm','XTerm*disallowedTcapOps:', '-xrm','XTerm*termName:xterm-256color'])
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--xterm',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    folder=args.output.with_suffix('');folder.mkdir(parents=True,exist_ok=False)
    r,w=os.pipe();proc=subprocess.Popen(['Xvfb','-displayfd',str(w),'-screen','0','1024x768x24','-nolisten','tcp'],pass_fds=[w]);os.close(w);display=':'+os.read(r,100).decode().strip();os.close(r)
    owner=ObservedDisplay(display);harness.Display=ObservedDisplay
    result=dict(completed=False, executable_sha256=hashlib.sha256(Path(args.xterm).read_bytes()).hexdigest(), cases={})
    try:
        result['keyboard']=prepare_keyboard(owner,{'Shift_L','Control_L','BackSpace','Delete'})
        for name,spec in plans().items():
            row=harness.capture_case(args.xterm,display,name,spec,folder);result['cases'][name]=row
            assert row['completed'] and row['exit_code']==0 and len(row['steps'])==len(spec['steps'])
            write(args.output,result)
        result['completed']=True
    finally:
        write(args.output,result);owner.close();proc.terminate();proc.wait(timeout=5)

if __name__=='__main__':main()
