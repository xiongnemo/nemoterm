"""Observe the two rxvt scrollback modes in a fresh terminal per startup profile."""
import argparse
import os
from pathlib import Path

CSI = '\x1b['
PAIR = CSI+'?1010$p'+CSI+'?1011$p'
PROFILES = ((False,False),(False,True),(True,False),(True,True))


def stages():
    changes = {
        'startup':'', 'restore-before-save':CSI+'?1010;1011r',
        'both-off':CSI+'?1010;1011l', 'output-on':CSI+'?1010h',
        'save-both':CSI+'?1010;1011s', 'opposite':CSI+'?1011h'+CSI+'?1010l',
        'restore-output':CSI+'?1010r', 'restore-key':CSI+'?1011r',
        'save-key-only':CSI+'?1011h'+CSI+'?1011s', 'both-off-again':CSI+'?1010;1011l',
        'restore-reversed':CSI+'?1011;1010r', 'soft-reset-after-off':CSI+'?1010;1011l'+CSI+'!p',
        'soft-reset-after-on':CSI+'?1010;1011h'+CSI+'!p',
        'alternate':CSI+'?1011l'+CSI+'?1049h', 'back-from-alternate':CSI+'?1010l'+CSI+'?1049l',
        'hard-reset-after-on':CSI+'?1010;1011h'+'\x1bc', 'hard-reset-after-off':CSI+'?1010;1011l'+'\x1bc',
        'restore-after-hard-reset':CSI+'?1010;1011r',
    }
    return {name:change+PAIR for name,change in changes.items()}


def main():
    from xterm_state_oracle import run_cases
    p=argparse.ArgumentParser();p.add_argument('--xterm',required=True);p.add_argument('--directory',type=Path,required=True);args=p.parse_args()
    if os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise RuntimeError('GitHub-hosted runner required')
    args.directory.mkdir(parents=True,exist_ok=False)
    for output,key in PROFILES:
        run_cases(args.xterm,args.directory/f'{int(output)}{int(key)}.json',stages(),
                  ['-xrm',f'*scrollTtyOutput: {str(output).lower()}','-xrm',f'*scrollKey: {str(key).lower()}'],raw_replies=True)


if __name__=='__main__':main()
