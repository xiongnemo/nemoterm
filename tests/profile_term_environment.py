"""Record terminal identity from the actual saved profile child, including @name launches."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback

NAMES = ('TERM', 'COLORTERM', 'TERM_PROGRAM')
EXPECTED = dict(zip(NAMES, ('xterm-256color', 'truecolor', 'nemoterm')))


def main():
    from owned_job import OwnedJob
    from protocol_oracle_window import saved_profile
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise SystemExit('Requires a GitHub-hosted Windows runner')
    root = Path(__file__).resolve().parents[1]
    exe = Path(os.environ['NEMOTERM_TEST_EXE']).resolve(strict=True)
    data = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), expected=EXPECTED, cases={})
    with tempfile.TemporaryDirectory(prefix='profile-term-') as temporary:
        for style in ('option','at-name'):
            for parent in ('unset','different','already-listed'):
                name = style+'-'+parent; row = data['cases'][name] = dict(passed=False)
                path = Path(temporary)/(name+'.json'); env = os.environ.copy()
                for k in NAMES:
                    env.pop(k,None)
                if parent == 'different': env.update(TERM='dumb',COLORTERM='parent-color',TERM_PROGRAM='parent-terminal')
                inherited = None if parent=='unset' else 'KEEP_中/lp:COLORTERM_EXTRA/u:TERM_PROGRAM/w:TERM/u:'
                if parent=='already-listed':inherited='TERM/u:COLORTERM:KEEP_中/lp:TERM_PROGRAM/u'
                if inherited is None:env.pop('WSLENV',None)
                else:env['WSLENV']=inherited
                expected_exports='TERM/u:COLORTERM/u:TERM_PROGRAM/u' if inherited is None else inherited+'COLORTERM/u'
                if parent=='already-listed':expected_exports=inherited
                row['expected_exports']=expected_exports
                row['parent'] = {k:env.get(k) for k in NAMES}
                env['NEMOTERM_CONPTY']='bundled'
                command = subprocess.list2cmdline([sys.executable,str(Path(__file__).resolve()),'--child',str(path)])
                try:
                    with saved_profile(dict(NemoShell='custom',NemoShellCommand=command,NemoTabs=0,WarnOnClose=0,CloseOnExit=1)) as profile, OwnedJob() as job:
                        args=['--profile',profile[1]] if style=='option' else ['@'+profile[1]]
                        proc=job.spawn([str(exe),*args],env=env,creationflags=subprocess.CREATE_NO_WINDOW)
                        row['exit_code']=proc.wait(timeout=25)
                        row['cleanup']=job.finish()
                        row['child']=json.loads(path.read_text(encoding='utf-8'))
                        row['passed']=(row['exit_code']==0 and not row['cleanup']['terminated_remaining'] and row['cleanup']['after']['active']==0 and row['child']==dict(EXPECTED,WSLENV=expected_exports))
                except Exception: row['error']=traceback.format_exc()
    data['completed']=all(r['passed'] for r in data['cases'].values())
    (root/'research'/'profile-term-environment.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:[r.get('child'),r['passed'],r.get('error')] for k,r in data['cases'].items()}),flush=True)
    return 0 if data['completed'] else 1


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--child':
        Path(sys.argv[2]).write_text(json.dumps({k:os.environ.get(k) for k in (*NAMES,'WSLENV')}),encoding='utf-8')
    else:
        raise SystemExit(main())
