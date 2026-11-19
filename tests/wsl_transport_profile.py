"""Toggle the WSL transport from live settings and reopen a plain WSL Bash profile."""
import hashlib
import json
import os
import re
from pathlib import Path
import shlex
import subprocess
import sys
import traceback
import uuid
import winreg
from hosted_gesture_input import DesktopInput
from native_test_utils import root, wait_for
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile

sys.path.insert(0,str(root/'tools'))
import nemoterm_debug as api


def exercise():
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted' and os.environ.get('GITHUB_ACTIONS')=='true'
    assert 'NEMOTERM_WSL_PTY_RELAY' not in os.environ
    exe=Path(os.environ['NEMOTERM_TEST_EXE']).resolve();font=os.environ['NEMOTERM_TEST_FONT']
    expected=os.environ['NEMOTERM_TEST_RELAY_SHA256'];folder=root/'research/wsl-transport-profile';folder.mkdir()
    result=dict(completed=False,executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),font=font,relay_sha256=expected,launches=[])
    try:
        with saved_profile({'NemoShell':'wsl-bash','NemoRenderer':0,'WarnOnClose':0,'CloseOnExit':1}) as flags:
            key='Software\\Nemo\\Nemoterm\\Sessions\\'+flags[1]
            def saved():
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as h:
                    try:return winreg.QueryValueEx(h,'NemoWslLinuxPty')[0]
                    except FileNotFoundError:return None
            for label,active,change in [('default',False,True),('windows-shell',False,None),('enabled',True,False),('disabled',False,None)]:
                temp=folder/(label+' session files');temp.mkdir()
                rec=dict(stage=label,saved_before=saved());result['launches'].append(rec)
                assert rec['saved_before']=={'default':None,'windows-shell':1,'enabled':1,'disabled':0}[label]
                env=dict(os.environ,TEMP=str(temp),TMP=str(temp));env.pop('NEMOTERM_TEST_WSL_PROFILE_PTY',None)
                # No -e or custom WSL command: exercise the installed shell selected by the profile.
                extra=['--shell','powershell'] if label=='windows-shell' else []
                with OwnedJob() as job:
                    proc=job.spawn([str(exe),*flags,'--tabs' if label=='default' else '--no-tabs','--automation','--font',font,*extra],env=env,creationflags=subprocess.CREATE_NO_WINDOW)
                    try:
                        inst=wait_for(lambda:next(iter(api.discover(proc.pid)),None),timeout=30);seat,=inst['sessions']
                        pattern = r'^PS [^\r\n]*>\s*$' if label=='windows-shell' else r'^[^\r\n]*[$#]\s*$'
                        def prompt():
                            lines=api.request(inst['endpoint'],'text',seat['id']).splitlines()
                            return next((line.rstrip() for line in reversed(lines) if re.fullmatch(pattern,line)),None)
                        rec['initial_prompt']=wait_for(prompt,timeout=30)
                        def send(text):api.request(inst['endpoint'],'input',seat['id'],text+'\r')
                        def identify(step, is_relay=active):
                            tag=uuid.uuid4().hex;path=folder/(tag+'.txt')
                            linux='/mnt/'+path.drive[0].lower()+path.as_posix()[2:];dest=shlex.quote(linux);writing=shlex.quote(linux[:-4]+'.tmp')
                            # The marker is only acknowledged after the guest atomically publishes its own record.
                            send("{ printf '%s\\n' \"$$\" \"$PPID\" \"$BASH_VERSION\"; tty; readlink /proc/\"$PPID\"/exe || :; sha256sum /proc/\"$PPID\"/exe 2>/dev/null || :; } > "+writing+' && mv '+writing+' '+dest)
                            wait_for(path.exists,timeout=30);fields=path.read_text(encoding='utf-8').splitlines()
                            assert len(fields)>=4 and fields[0].isdigit() and fields[1].isdigit() and fields[2] and fields[3].startswith('/dev/'),fields
                            files=list(temp.glob('nemoterm-wsl-*.elf'));observed=dict(pid=fields[0],ppid=fields[1],bash=fields[2],tty=fields[3],parent=fields[4:],files=[f.name for f in files]);rec[step]=observed
                            if is_relay:
                                assert len(fields)==6 and fields[3].startswith('/dev/pts/') and len(files)==1,observed
                                assert fields[4].endswith('/'+files[0].name) and fields[5].split()[0]==hashlib.sha256(files[0].read_bytes()).hexdigest()==expected,observed
                            else:assert not files and not any(expected in f for f in fields[4:]),observed
                            return observed
                        if label=='windows-shell':
                            path=folder/'powershell.txt';send("[IO.File]::WriteAllText('"+str(path).replace("'","''")+"',$PSVersionTable.PSEdition)")
                            wait_for(lambda:path.is_file() and path.read_text()=='Desktop',timeout=25)
                            rec['edition']='Desktop';assert not list(temp.glob('nemoterm-wsl-*.elf'))
                        else:
                            before=identify('before')
                            if change is not None:
                                cmd=['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(root/'tests/owned_profile_settings.ps1'),'-Action','wsl-pty-'+('on' if change else 'off'),'-TargetProcess',str(proc.pid),'-TargetWindow',str(seat['hwnd'])]
                                ui=subprocess.run(cmd,capture_output=True,timeout=65);rec['settings']=dict(exit=ui.returncode,log=(ui.stdout+ui.stderr).decode(errors='replace'));ui.check_returncode()
                                rec['saved_after']=saved();assert rec['saved_after']==int(change)
                                assert identify('after_save')==before,'Save and Apply changed the live shell or its transport'
                                if label=='default':
                                    # The ordinary new-tab shortcut must use the setting just saved, without
                                    # changing the already connected shell or restarting the frontend.
                                    first=seat
                                    desk=DesktopInput(proc.pid,seat['window'],seat['hwnd'],rec.setdefault('new_tab_keyboard',{}))
                                    try:desk.chord(0x11,0x10,ord('T'))
                                    finally:desk.restore()
                                    def new_tab():
                                        seats=api.request(inst['endpoint'])['sessions']
                                        return next((s for s in seats if s['id']!=first['id']),None) if len(seats)==2 else None
                                    seat=wait_for(new_tab,timeout=25)
                                    assert seat['window']==first['window'] and seat['hwnd']!=first['hwnd']
                                    rec['tab_ids']=[first['id'],seat['id']];wait_for(prompt,timeout=30)
                                    fresh=identify('new_tab',True);assert fresh['pid']!=before['pid']
                                    send('exit');seat=first
                                    wait_for(lambda:[s['id'] for s in api.request(inst['endpoint'])['sessions']]==[first['id']])
                                    wait_for(lambda:not list(temp.glob('nemoterm-wsl-*.elf')))
                                    assert identify('after_tab_close')==before
                        send('exit');rec['exit_code']=proc.wait(timeout=20);assert rec['exit_code']==0
                    finally:rec['cleanup']=job.finish(grace=4)
                rec['residual_files']=[f.name for f in temp.glob('nemoterm-wsl-*.elf')];assert not rec['cleanup']['terminated_remaining'] and not rec['residual_files']
        result['completed']=True
    except Exception:result['error']=traceback.format_exc();raise
    finally:(folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')


if __name__=='__main__':exercise()
