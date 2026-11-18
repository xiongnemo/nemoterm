"""Observe the VT bytes a real child receives for a single image paste action."""
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import traceback

from agent_clipboard_fixture import put_bitmap
from clipboard_test_utils import SavedClipboard
from fixture_io import read_snapshot, write_snapshot
from native_test_utils import wait_for
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import nemoterm_debug as api


def run():
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    exe=Path(os.environ['NEMOTERM_TEST_EXE']).resolve(strict=True)
    font=os.environ['NEMOTERM_TEST_FONT']
    evidence=dict(font=font,executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),cases={})
    out=ROOT/'build/image-key-records/image-protocol.json';out.parent.mkdir(parents=True,exist_ok=True)
    # One synthetic application action is Ctrl+V, even if the configured terminal
    # binding includes Shift. Report release only for protocols requesting it.
    csi='\x1b[';ack=b'\x1b[0n';press=b'\x1b[118;5u';up=b'\x1b[118;5:3u'
    modes=[('legacy','',b'\x16'),('kitty-disambiguate',csi+'>1u',press),
           ('kitty-events',csi+'=3u',press+up),('kitty-all',csi+'=31u',press+up),
           ('kitty-pop',csi+'<u',b'\x16'),('xterm-level-1',csi+'>4;1m',b'\x16'),
           ('xterm-level-2',csi+'>4;2m',b'\x1b[27;5;118~'),('xterm-disabled',csi+'>4;0m',b'\x16')]
    with tempfile.TemporaryDirectory() as tmp, saved_profile(dict(NemoRenderer=0,WarnOnClose=0,CloseOnExit=1,NemoFormatOtherKeys=0)) as args, OwnedJob() as job:
        report=Path(tmp)/'rx.json'; control=Path(tmp)/'control.json'
        proc=job.spawn([str(exe),*args,'--automation','--font',font,'-e',sys.executable,
            str(ROOT/'tests/mouse_fixture.py'),str(report),str(control),'180'],creationflags=subprocess.CREATE_NO_WINDOW,
            env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1'))
        try:
            inst=wait_for(lambda:next(iter(api.discover(proc.pid)),None));sess,=inst['sessions'];sid=sess['id']
            saved=SavedClipboard(sess['hwnd'])
            try:
                put_bitmap(sess['hwnd'])
                for name,mode,expected in modes:
                    row=evidence['cases'][name]=dict(expected=expected.hex(),mode=mode.encode().hex(),passed=False)
                    def current():
                        v=read_snapshot(report);assert proc.poll() is None and not v.get('error'),v
                        return bytes.fromhex(v['hex']) if v.get('phase')==name else b''
                    req=dict(phase=name,sequence=mode+csi+'5n');write_snapshot(control,req)
                    wait_for(lambda:current()==ack)
                    api.request(inst['endpoint'],'key',sid,struct.pack('<II',ord('V'),3))
                    wait_for(lambda:len(current())>len(ack))
                    write_snapshot(control,dict(req,input_barrier=1))
                    wait_for(lambda:read_snapshot(report).get('input_barrier')==1)
                    raw=current();assert raw.startswith(ack) and raw.endswith(ack),raw
                    row.update(received=raw[len(ack):-len(ack)].hex(),passed=raw==ack+expected+ack)
                    write_snapshot(out,evidence)
            finally:saved.restore()
        except Exception:evidence['error']=traceback.format_exc()
        finally:
            write_snapshot(control,dict(stop=True));evidence['exit_code']=proc.wait(timeout=15)
            evidence['cleanup']=job.finish();write_snapshot(out,evidence)
    for name,row in evidence['cases'].items():print(name,row,flush=True)
    if 'error' in evidence:print(evidence['error'],flush=True)
    return (not evidence.get('error') and len(evidence['cases'])==len(modes) and all(x['passed'] for x in evidence['cases'].values())
            and evidence['exit_code']==0 and not evidence['cleanup']['terminated_remaining'])

if __name__=='__main__':sys.exit(0 if run() else 1)
