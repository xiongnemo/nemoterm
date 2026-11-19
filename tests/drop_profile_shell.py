"""Verify shell-specific quoting across Save and Apply, using two actual shells."""
import hashlib
import os
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


def exercise(renderer):
    exe = Path(os.environ['NEMOTERM_TEST_EXE'])
    font = os.environ['NEMOTERM_TEST_FONT']
    folder = root/'research'/f'drop-profile-{renderer}'
    folder.mkdir()
    report = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), font=font, sessions={})
    with saved_profile({'NemoShell':'powershell', 'NemoRenderer':renderer-1, 'WarnOnClose':0, 'CloseOnExit':1}) as flags:
        key = "\\".join((r"Software\Nemo\Nemoterm\Sessions", flags[1]))
        for shell in ('powershell','cmd'):
            record = report['sessions'][shell] = dict(drops={})
            try:
                with OwnedJob() as job:
                    proc = job.spawn([str(exe), *flags, '--font', font, '--no-tabs', '--automation', '--cols','130','--rows','38'],creationflags=subprocess.CREATE_NO_WINDOW)
                    inst = wait_for(lambda:next(iter(api.discover(proc.pid)),None),timeout=25)
                    seat = inst['sessions'][0]; hwnd = seat['hwnd']; ep = inst['endpoint']; sid = seat['id']
                    u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
                    record['renderer']=int(u.GetPropW(hwnd,'NemotermRenderer') or 0);assert record['renderer']==renderer
                    def screen(): return api.request(ep,'text',sid)
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
                    barrier()
                    if shell=='cmd':
                        send('echo %COMSPEC%\r'); snapshot=barrier()
                        assert any(line.strip().lower().endswith('\\cmd.exe') and 'echo ' not in line.lower() for line in snapshot.splitlines()),snapshot
                    else:
                        send('$PSVersionTable.PSEdition\r');read_line('Desktop')
                    for stage in (('before-save','after-save') if shell=='powershell' else ('next-launch',)):
                        if stage=='after-save':
                            driver=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(root/'tests/owned_profile_settings.ps1'),'-Action','shell-cmd','-TargetProcess',str(proc.pid),'-TargetWindow',str(hwnd)],capture_output=True,timeout=65)
                            record['settings']=dict(exit=driver.returncode,log=(driver.stdout+driver.stderr).decode(errors='replace'))
                            driver.check_returncode()
                            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as h: record['persisted_shell']=winreg.QueryValueEx(h,'NemoShell')[0]
                            assert record['persisted_shell']=='cmd'
                        # The file contents never appear in a command or in the dropped path.
                        token='FILE_'+uuid.uuid4().hex
                        path=folder/(stage+" ' $nemoDropPath.txt")
                        path.write_text(token+'\n',encoding='ascii')
                        cmd='Get-Content -LiteralPath ' if shell=='powershell' else 'type '
                        send(cmd)
                        handle=block(drop_data([str(path)]))
                        try:
                            assert u.PostMessageW(hwnd,0x233,handle,0)
                            wait_for(lambda:stage in screen() and 'nemoDropPath.txt' in screen().split(stage)[-1],timeout=12)
                            send('\r'); snapshot=barrier()
                        finally:k.GlobalFree(handle)
                        record['drops'][stage]=dict(file=path.name,marker=token,screen=snapshot,opened=any(line.strip()==token for line in snapshot.splitlines()))
                    send('exit\r'); record['exit']=proc.wait(timeout=15)
                    record['cleanup']=job.finish();assert record['exit']==0 and not record['cleanup']['terminated_remaining']
            except Exception:record['error']=traceback.format_exc()
            finally:write_snapshot(folder/'result.json',report)
    return all('error' not in v and all(d['opened'] for d in v['drops'].values()) for v in report['sessions'].values())


if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    results=[exercise(renderer) for renderer in (1,3)]
    assert all(results),'See the actual commands, profile persistence and opened file markers in result.json'
