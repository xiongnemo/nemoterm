"""Verify shell-specific quoting across Save and Apply, using two actual shells."""
import hashlib
import os
import re
import time
from pathlib import Path
import subprocess
import sys
import traceback
import uuid
import winreg

from drop_window_smoke import block, drop_data
from fixture_io import write_snapshot
from native_test_utils import k, root, u, w, wait_for
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile

sys.path.insert(0, str(root/'tools'))
import nemoterm_debug as api


def exercise(renderer, after_prompt=False):
    exe = Path(os.environ['NEMOTERM_TEST_EXE'])
    font = os.environ['NEMOTERM_TEST_FONT']
    folder = root/'research'/f'drop-{"prompt-" if after_prompt else ""}profile-{renderer}'
    folder.mkdir()
    report = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), font=font, after_prompt=after_prompt, sessions={})
    with saved_profile({'NemoShell':'powershell', 'NemoRenderer':renderer-1, 'WarnOnClose':0, 'CloseOnExit':1}) as flags:
        key = "\\".join((r"Software\Nemo\Nemoterm\Sessions", flags[1]))
        for shell in ('powershell','cmd'):
            record = report['sessions'][shell] = dict(drops={})
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as profile:
                record['configured_shell_at_launch']=winreg.QueryValueEx(profile,'NemoShell')[0]
            started=time.monotonic()
            def elapsed(): return round((time.monotonic()-started)*1000,1)
            try:
                with OwnedJob() as job:
                    proc = job.spawn([str(exe), *flags, '--font', font, '--no-tabs', '--automation', '--cols','130','--rows','38'],creationflags=subprocess.CREATE_NO_WINDOW)
                    inst = wait_for(lambda:next(iter(api.discover(proc.pid)),None),timeout=25)
                    record['discovered_ms']=elapsed()
                    seat = inst['sessions'][0]; hwnd = seat['hwnd']; ep = inst['endpoint']; sid = seat['id']
                    u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
                    record['renderer']=int(u.GetPropW(hwnd,'NemotermRenderer') or 0);assert record['renderer']==renderer
                    def screen():
                        record['last_screen']=api.request(ep,'text',sid)
                        return record['last_screen']
                    def read_line(marker):
                        def check():
                            text=screen()
                            return text if marker in (line.strip() for line in text.splitlines()) else None
                        return wait_for(check,timeout=18)
                    def send(text): api.request(ep,'input',sid,text)
                    def barrier():
                        marker='DONE_'+uuid.uuid4().hex
                        send('echo '+marker+'\r')
                        return read_line(marker)
                    if after_prompt:
                        pattern=re.compile((r'PS ' if shell=='powershell' else '')+r'[A-Za-z]:\\[^<>]*>')
                        def prompt():
                            return next((line.strip() for line in screen().splitlines() if pattern.fullmatch(line.strip())), None)
                        record['first_prompt']=wait_for(prompt,timeout=18)
                        record['first_prompt_ms']=elapsed()
                    # Exactly one command; retain a missed acknowledgment in cold mode.
                    marker='DONE_'+uuid.uuid4().hex
                    record['probe']={'marker':marker,'sent_ms':elapsed()}
                    reply=api.request(ep,'input',sid,'echo '+marker+'\r')
                    record['probe']['input_reply']=reply.hex() if isinstance(reply,bytes) else reply
                    try: read_line(marker)
                    finally: record['probe'].update(finished_ms=elapsed(), process_exit=proc.poll(), job=job.accounting())
                    if shell=='cmd':
                        send('prompt $G\r');send('echo %COMSPEC%\r'); snapshot=barrier()
                        assert any(line.strip().lower().endswith('\\cmd.exe') and 'echo ' not in line.lower() for line in snapshot.splitlines()),snapshot
                    else:
                        send("function prompt { 'P> ' }\r");send('$PSVersionTable.PSEdition\r');read_line('Desktop')
                    for stage in (('before-save','after-save') if shell=='powershell' else ('next-launch',)):
                        if stage=='after-save':
                            driver=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(root/'tests/owned_profile_settings.ps1'),'-Action','shell-cmd','-TargetProcess',str(proc.pid),'-TargetWindow',str(hwnd)],capture_output=True,timeout=65)
                            record['settings']=dict(exit=driver.returncode,log=(driver.stdout+driver.stderr).decode(errors='replace'))
                            driver.check_returncode()
                            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as h: record['persisted_shell']=winreg.QueryValueEx(h,'NemoShell')[0]
                            assert record['persisted_shell']=='cmd'
                        # The file contents never appear in a command or in the dropped path.
                        for kind in (('file','folder') if after_prompt else ('file',)):
                            token='FILE_'+uuid.uuid4().hex
                            tail=uuid.uuid4().hex[:8]+('.txt' if kind=='file' else '.dir')
                            path=folder/("a ' $nemoDropPath."+tail)
                            if kind=='file':
                                path.write_text(token+'\n',encoding='ascii')
                                cmd='Get-Content -LiteralPath ' if shell=='powershell' else 'type '
                            else:
                                path.mkdir(); token='MEMBER_'+uuid.uuid4().hex+'.txt'
                                (path/token).write_text('member\n',encoding='ascii')
                                cmd='Get-ChildItem -Name -LiteralPath ' if shell=='powershell' else 'dir /b '
                            case=stage+'-'+kind if after_prompt else stage
                            drop=record['drops'][case]=dict(file=path.name,kind=kind,marker=token,opened=False)
                            send(cmd)
                            handle=block(drop_data([str(path)]))
                            try:
                                assert u.PostMessageW(hwnd,0x233,handle,0)
                                wait_for(lambda:tail in ''.join(line.rstrip() for line in screen().splitlines()),timeout=12)
                                send('\r');snapshot=barrier()
                            finally:k.GlobalFree(handle)
                            drop.update(screen=snapshot, opened=any(line.strip()==token for line in snapshot.splitlines()))
                    send('exit\r'); record['exit']=proc.wait(timeout=15)
                    record['cleanup']=job.finish();assert record['exit']==0 and not record['cleanup']['terminated_remaining']
            except Exception:record['error']=traceback.format_exc()
            finally:write_snapshot(folder/'result.json',report)
    for shell, stages in [('powershell',('before-save','after-save')),('cmd',('next-launch',))]:
        v=report['sessions'][shell]
        expected={stage+'-'+kind for stage in stages for kind in ('file','folder')} if after_prompt else set(stages)
        if 'error' in v or set(v['drops'])!=expected or not all(d['opened'] for d in v['drops'].values()): return False
    return True


if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    assert sys.argv[1:] in ([],['--after-prompt'])
    results=[exercise(renderer,after_prompt=bool(sys.argv[1:])) for renderer in (1,3)]
    assert all(results),'See the actual commands, profile persistence and opened file markers in result.json'
