"""Observe the VT bytes a real child receives for a single image paste action."""
import argparse
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import traceback

from agent_clipboard_fixture import bitmap_bytes, put_bitmap, put_clipboard_blocks
from clipboard_test_utils import SavedClipboard
from fixture_io import read_snapshot, write_snapshot
from native_test_utils import wait_for
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import nemoterm_debug as api


def run(mixed=False):
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    exe=Path(os.environ['NEMOTERM_TEST_EXE']).resolve(strict=True)
    font=os.environ['NEMOTERM_TEST_FONT']
    evidence=dict(font=font,executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),cases={})
    out=ROOT/'build/image-key-records'/('mixed-formats.json' if mixed else 'image-protocol.json');out.parent.mkdir(parents=True,exist_ok=True)
    # One synthetic application action is Ctrl+V, even if the configured terminal
    # binding includes Shift. Report release only for protocols requesting it.
    csi='\x1b[';ack=b'\x1b[0n';press=b'\x1b[118;5u';up=b'\x1b[118;5:3u'
    modes=[('legacy','',b'\x16'),('kitty-disambiguate',csi+'>1u',press),
           ('kitty-events',csi+'=3u',press+up),('kitty-all',csi+'=31u',press+up),
           ('kitty-pop',csi+'<u',b'\x16'),('xterm-level-1',csi+'>4;1m',b'\x16'),
           ('xterm-level-2',csi+'>4;2m',b'\x1b[27;5;118~'),('xterm-csi-u',csi+'>4;1f',press),
           ('kitty-over-xterm',csi+'>3u',press+up),('back-to-xterm',csi+'<u',press),
           ('xterm-disabled',csi+'>4;0m',b'\x16')]
    if mixed:
        image=(8,bitmap_bytes()); utf16=lambda text:(13,(text+'\0').encode('utf-16le')); ansi=lambda text:(1,text+b'\0')
        wrap=lambda data:b'\x1b[200~'+data+b'\x1b[201~'
        cases=[('dib-only',[image],b'\x16'), ('empty-unicode-first',[utf16(''),image],b'\x16'),
               ('empty-unicode-last',[image,utf16('')],b'\x16'), ('empty-ansi',[ansi(b''),image],b'\x16'),
               ('both-empty',[utf16(''),ansi(b''),image],b'\x16'),
               ('distinct-ansi',[utf16(''),ansi(b'fallback'),image],wrap(b'fallback')),
               ('text-first',[utf16('正文'),image],wrap('正文'.encode())),
               ('image-first',[image,utf16('正文')],wrap('正文'.encode())),
               ('spaces',[utf16('  '),image],wrap(b'  ')), ('empty-no-image',[utf16('')],b'')]
        formats={name:items for name,items,_ in cases}
        modes=[(name,csi+'?2004h',expected) for name,_,expected in cases]
    with tempfile.TemporaryDirectory() as tmp, saved_profile(dict(NemoRenderer=0,WarnOnClose=0,CloseOnExit=1,NemoFormatOtherKeys=0)) as args, OwnedJob() as job:
        report=Path(tmp)/'rx.json'; control=Path(tmp)/'control.json'
        proc=job.spawn([str(exe),*args,'--automation','--font',font,'-e',sys.executable,
            str(ROOT/'tests/mouse_fixture.py'),str(report),str(control),'180'],creationflags=subprocess.CREATE_NO_WINDOW,
            env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1',
                     **({'NEMOTERM_TEST_UTF8_INPUT':'1','NEMOTERM_TEST_WIDE_INPUT':'1'} if mixed else {})))
        try:
            inst=wait_for(lambda:next(iter(api.discover(proc.pid)),None));sess,=inst['sessions'];sid=sess['id']
            saved=SavedClipboard(sess['hwnd'])
            try:
                if not mixed:put_bitmap(sess['hwnd'])
                for name,mode,expected in modes:
                    row=evidence['cases'][name]=dict(expected=expected.hex(),mode=mode.encode().hex(),passed=False)
                    if mixed:
                        put_clipboard_blocks(sess['hwnd'],formats[name]);row['published_formats']=[fmt for fmt,_ in formats[name]]
                    def current():
                        v=read_snapshot(report);assert proc.poll() is None and not v.get('error'),v
                        return bytes.fromhex(v['hex']) if v.get('phase')==name else b''
                    req=dict(phase=name,sequence=mode+csi+'5n');write_snapshot(control,req)
                    wait_for(lambda:current()==ack)
                    # Place a barrier after the action, not a sleep: partial or
                    # duplicate reports should remain visible in the comparison.
                    def chord(mods,barrier,prefix):
                        api.request(inst['endpoint'],'key',sid,struct.pack('<II',ord('V'),mods))
                        if mixed:
                            # Even a swallowed action must reach its trailing barrier and
                            # leave the independent cases available for comparison.
                            try:wait_for(lambda:len(current())>len(prefix),timeout=2)
                            except AssertionError:
                                current()  # Propagate terminal or fixture errors.
                        else:wait_for(lambda:len(current())>len(prefix))
                        write_snapshot(control,dict(req,input_barrier=barrier))
                        wait_for(lambda:read_snapshot(report).get('input_barrier')==barrier)
                        raw=current();assert raw.startswith(prefix) and raw.endswith(ack),raw
                        return raw[len(prefix):-len(ack)],raw
                    received,prefix=chord(3,1,ack)
                    row.update(received=received.hex(),passed=received==expected)
                    if not mixed and len(expected)>1:
                        # Ctrl+V is not a terminal binding in these modes. Its
                        # down/up messages take the normal keyboard translator.
                        reference,_=chord(2,2,prefix)
                        row.update(ordinary_ctrl_v=reference.hex(),passed=reference==received==expected)
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

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mixed-formats', action='store_true')
    sys.exit(0 if run(parser.parse_args().mixed_formats) else 1)
