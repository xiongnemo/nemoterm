"""Capture column-mode changes, cursor, screen size and individual screen cells."""
from pathlib import Path
import argparse,json,os

C = '\x1b['
PAINT = C+'2;3HA中Z'+C+'7;11H'
# Select positive codepoint checksums including unwritten/blank cells. Keep
# coordinates absolute (origin mode is off throughout the experiment).
PROBE = ''.join(C+f'?{m}$p' for m in (3,40,95))+C+'6n'+C+'18t'+C+'31#y'+''.join(C+f'{x};1;2;{x};2;{x}*y' for x in range(3,7))

def stages(profile):
    init = {'enabled':'','disabled':C+'?40l','level4':C+'64;1"p',
            'explicit-80':C+'?40h','explicit-off':C+'?40l','explicit-level4':C+'64;1"p'+C+'?40h'}[profile]
    actions = [('initial',init),('paint',PAINT),('set-132',C+'?3h'),('read-132',''),('back-80',C+'?3l'),
               ('enable-keep',C+'?40;95h'+PAINT),('keep-widen',C+'?3h'),('read-wide',''),
               ('keep-narrow',C+'?3l'),('read-narrow',''),('same-80',PAINT+C+'?3l'),
               ('disable-switch',C+'?40l'+PAINT),('ignored-132',C+'?3h'),
               ('save',C+'?40;95s'),('opposite',C+'?40h'+C+'?95l'),('restore',C+'?40;95r'),
               ('alternate',C+'?1049h'),('back-main',C+'?1049l'),('soft-reset',C+'!p'),('hard-reset','\x1bc'),
               ('allow-clear',C+'?40h'+C+'?95l'+PAINT),('same-width-clear',C+'?3l')]
    return {name:sequence+PROBE for name,sequence in actions}


def reference(exe,out):
    from xterm_state_oracle import run_cases
    out.mkdir(parents=True,exist_ok=False)
    for k in ('enabled','disabled','level4','explicit-80','explicit-off','explicit-level4'):
        run_cases(exe,out/(k+'.json'),stages(k),['-ti','vt520','+132' if k.startswith('explicit-') else '-132','-xrm','*allowWindowOps: true'],raw_replies=True)
    from column_mode_saved_cases import QUERY, saved_cases
    for name, args, initial_132 in [('on',['-132'],True), ('off',['+132'],False), ('auto',[],False)]:
        sequences = {key: command+QUERY for key,command,*_ in saved_cases(True,initial_132)}
        run_cases(exe,out/('saved-'+name+'.json'),sequences,['-ti','vt520',*args,'-xrm','*allowWindowOps: true'],raw_replies=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--xterm',required=True);p.add_argument('--directory',type=Path,required=True);a=p.parse_args()
    if os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise RuntimeError('Requires a GitHub-hosted runner')
    reference(a.xterm,a.directory)
