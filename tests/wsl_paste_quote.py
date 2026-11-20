"""Physical Windows paste into a real WSL tty, in raw and canonical mode."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import traceback
import zipfile
from clipboard_test_utils import SavedClipboard, set_clipboard
from fixture_io import read_snapshot
from hosted_gesture_input import DesktopInput
from native_test_utils import c,w,u,root,find_window,terminal_host,wait_for
from owned_job import OwnedJob
from wsl_job_observation import job_images, finish_observed
from protocol_oracle_window import saved_profile
from xterm_paste_lines import TEXT


def unix(p):return '/mnt/'+p.drive[0].lower()+p.as_posix()[2:]

def exercise(renderer,lnext,reference):
    folder=root/'research'/f'wsl-paste-quote-{renderer}-{lnext}';folder.mkdir()
    peer=Path(__file__).resolve().with_name('wsl_paste_peer.py');exe=Path(os.environ['NEMOTERM_TEST_EXE']).resolve();font=os.environ['NEMOTERM_TEST_FONT'];distro=os.environ['NEMOTERM_TEST_WSL_DISTRO']
    r=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),peer_sha256=hashlib.sha256(peer.read_bytes()).hexdigest(),font=font,cases={},completed=False)
    profile={'NemoRenderer':renderer-1,'WarnOnClose':0,'CloseOnExit':1}
    bundled = os.environ.get('NEMOTERM_TEST_WSL_PROFILE_PTY')=='1'
    assert 'NEMOTERM_WSL_PTY_RELAY' not in os.environ
    if bundled: profile['NemoWslLinuxPty']=1
    r['transport_selection']='saved-profile' if bundled else 'default'
    child_env = dict(os.environ, NEMOTERM_CONPTY='bundled')
    child_env.pop('NEMOTERM_TEST_WSL_PROFILE_PTY',None)
    if bundled:
        session_temp=folder/'session files'
        session_temp.mkdir()
        child_env.update(TEMP=str(session_temp),TMP=str(session_temp))
    if lnext==29:profile['TerminalModes']='LNEXT=V^]'
    with saved_profile(profile) as flags,OwnedJob() as job:
        desk=clip=None
        try:
            proc=job.spawn([str(exe),'--no-tabs',*flags,'--cols','80','--rows','24','--font',font,'-e',str(Path(os.environ['SystemRoot'])/'System32'/'wsl.exe'),'--distribution',distro,'--exec','/usr/bin/python3',unix(peer),unix(folder),str(lnext),*(['--relay-parent'] if os.environ.get('NEMOTERM_TEST_RELAY_SHA256') else [])],env=child_env,creationflags=subprocess.CREATE_NO_WINDOW)
            hwnd=wait_for(lambda:find_window(proc.pid),timeout=25);u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
            r['renderer']=int(u.GetPropW(hwnd,'NemotermRenderer') or 0);assert r['renderer']==renderer
            desk=DesktopInput(proc.pid,terminal_host(hwnd),hwnd,r.setdefault('keyboard',{}));clip=SavedClipboard(hwnd);set_clipboard(hwnd,TEXT)
            def snapshot(name):
                value=read_snapshot(folder/name)
                if value:return value
                if proc.poll() is not None:raise ValueError(('WSL exited',proc.returncode,name))
            for stage,reference_name in [('raw-plain','default'),('raw-quote','quote'),('raw-all','all'),('canonical-quote',None)]:
                ready=wait_for(lambda:snapshot(stage+'-ready.json'),timeout=35)
                if stage=='raw-plain':
                    r.update(frontend_pid=proc.pid,job_at_ready=job_images(job))
                    if bundled:
                        files=list(session_temp.glob('nemoterm-wsl-*.elf'))
                        assert len(files)==1,files
                        r.update(relay_file=files[0].name,relay_sha256=hashlib.sha256(files[0].read_bytes()).hexdigest())
                        assert r['relay_sha256']==os.environ['NEMOTERM_TEST_RELAY_SHA256']
                begin=time.time_ns();desk.chord(0x11,0x10,ord('V'))
                if reference_name:wait_for(lambda:snapshot(stage+'-period.json'),timeout=15)
                desk.chord(0x0d);desk.chord(ord('7'))
                if not reference_name:desk.chord(0x0d)
                observed=wait_for(lambda:snapshot(stage+'-done.json'),timeout=18);observed.update(start_utc_ns=begin,end_utc_ns=time.time_ns());r['cases'][stage]=observed
                if reference_name:
                    ref=reference['cases'][reference_name];expected=bytes.fromhex(ref['paste_hex'])+b'\r7';mode=ref['mode_hex']
                else:
                    # Linux should consume VLNEXT itself, retain the embedded LFs,
                    # and return exactly one submitted line followed by the sentinel.
                    expected=TEXT.encode()+b'\n7\n';mode=reference['cases']['restore-lf']['mode_hex']
                    observed['line_reads_match']=observed['chunks']==[(TEXT.encode()+b'\n').hex(),b'7\n'.hex()]
                observed.update(expected_input=expected.hex(),mode_matches=ready['mode_hex']==mode,input_matches=observed['input_hex']==expected.hex())
            clip.restore();clip=None;desk.restore();desk=None
            (folder/'release').touch()
            assert proc.wait(timeout=15)==0;peer_result=read_snapshot(folder/'linux.json');assert peer_result['completed'] and r['peer_sha256']==peer_result['fixture_sha256']
            if os.environ.get('NEMOTERM_TEST_RELAY_SHA256'):
                assert peer_result['tty'].startswith('/dev/pts/') and peer_result['parent_sha256']==os.environ['NEMOTERM_TEST_RELAY_SHA256'], peer_result
            if bundled:
                assert peer_result['parent_exe'].endswith('/'+r['relay_file']),peer_result['parent_exe']
                r['relay_files_after_exit']=[p.name for p in session_temp.glob('nemoterm-wsl-*.elf')]
                assert not r['relay_files_after_exit']
            r['job_after_exit']=job_images(job);r['cleanup']=finish_observed(job)
            assert not r['cleanup']['grace_exceeded'] and not r['cleanup']['terminated_remaining'];r['completed']=True
        except BaseException:
            r['error']=traceback.format_exc();raise
        finally:
            try:
                if clip:clip.restore()
            finally:
                try:
                    if desk:desk.restore()
                    (folder/'release').touch()
                    r['cleanup']=job.finish()
                finally:
                    (folder/'result.json').write_text(json.dumps(r,indent=2))
    return all(v['mode_matches'] and v['input_matches'] and v.get('line_reads_match',True) for v in r['cases'].values())


if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    archive=root/'xterm412-paste-quote.zip';assert hashlib.sha256(archive.read_bytes()).hexdigest()=='3d06c7eec267dc31f6fc8c52e2fc2f0b85de3cb932f4bccca10ec31467c044c1'
    outcomes=[]
    with zipfile.ZipFile(archive) as z:
        for renderer in (1,3):
            for profile,lnext in [('default',22),('custom',29)]:
                ref=json.loads(z.read('paste-quote/'+profile+'.json'));assert ref['completed'] and ref['tty_lnext']==lnext
                try:outcomes.append(exercise(renderer,lnext,ref))
                except Exception:traceback.print_exc();outcomes.append(False)
    assert all(outcomes), 'Compare actual Linux raw tty input, canonical lines and independent mode replies in result.json'
