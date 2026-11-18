"""Real Codex/OpenCode image paste, with no live model or tool execution."""
import argparse
import json
import hashlib
import traceback
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
from fixture_io import read_snapshot,write_snapshot
from native_test_utils import u, wait_for
from owned_job import OwnedJob

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import nemoterm_debug as api


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client',choices=('codex','opencode'),required=True)
    parser.add_argument('--client-exe',required=True)
    parser.add_argument('--terminal',default=os.environ.get('NEMOTERM_TEST_EXE',str(ROOT/'dist/nemoterm.exe')))
    parser.add_argument('--font',default='SarasaTermSC Nerd Font Light')
    parser.add_argument('--system-input', action='store_true')
    parser.add_argument('--binding',choices=('ctrl-v','ctrl-shift-v'))
    args=parser.parse_args()
    folder=Path(tempfile.mkdtemp(prefix='agent-image-',dir=ROOT/'build'))
    result=dict(client=args.client,cases=[],live_model=False,tool_responses=False,font=args.font)
    result.update(system_input=args.system_input,failures=[])
    for name,mods in [('ctrl-v',2),('ctrl-shift-v',3)]:
        if args.binding and args.binding!=name:continue
        case=folder/name;report=case/'observed.json';control=case/'control.json'
        with OwnedJob() as job, (folder/(name+'.log')).open('w',encoding='utf-8') as log:
            process=job.spawn([sys.executable,str(ROOT/'tests/agent_clipboard_fixture.py'),
                '--client',args.client,'--client-exe',str(Path(args.client_exe).resolve()),
                '--terminal',str(Path(args.terminal).resolve()),'--directory',str(case),
                '--automation','--font',args.font],stdout=log,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
            desk=None;events={}
            try:
                observed=wait_for(lambda:read_snapshot(report),timeout=30)
                instance=wait_for(lambda:next(iter(api.discover(observed['pid'])),None),timeout=20)
                endpoint=instance['endpoint'];session,=instance['sessions'];seat=session['id']
                if args.system_input:
                    from hosted_gesture_input import DesktopInput
                    desk=DesktopInput(observed['pid'],session['window'],session['hwnd'],events)
                def key(vk,mods):
                    if desk:
                        keys={0:(),2:(0x11,),3:(0x11,0x10)}[mods];desk.chord(*keys,vk)
                    else:api.request(endpoint,'key',seat,struct.pack('<II',vk,mods))
                ready='Ask Codex' if args.client=='codex' else 'Ask anything'
                wait_for(lambda:ready in api.request(endpoint,'text',seat),timeout=60)
                marker='NEMOTERM_'+args.client.upper()+'_IMAGE_'+name.upper().replace('-','_')
                # A painted startup prompt is not an input-consumption ack.
                # Observe the application consume this prompt before asking
                # its asynchronous clipboard reader to attach an image.
                api.request(endpoint,'paste',seat,marker)
                wait_for(lambda:marker in api.request(endpoint,'text',seat),timeout=20)
                write_snapshot(control,dict(id=1,action='bitmap'))
                wait_for(lambda:read_snapshot(report).get('clipboard_action')==1)
                trace=case/'client-output.log'
                before=trace.read_bytes() if trace.is_file() else b''
                (case/'at-paste.vt').write_bytes(before)
                write_snapshot(case/'at-paste.json',dict(marker=marker,system=bool(desk),binding=name,
                    bytes=len(before),sha256=hashlib.sha256(before).hexdigest(),session=session))
                attachment_started=time.monotonic()
                key(86,mods)
                # OpenCode launches Windows PowerShell/WinForms to read images.
                # A fresh hosted runner exceeded 20 s, then painted the exact
                # attachment while a separate reader control also succeeded.
                wait_for(lambda:'[Image' in api.request(endpoint,'text',seat),
                         timeout=60 if args.client=='opencode' else 20)
                attachment_seconds=time.monotonic()-attachment_started
                time.sleep(.2)
                key(13,0)
                def received():
                    value=read_snapshot(report)
                    return value if value and any(marker in req['text'] and any(
                        im.get('generated_pixels_match') for im in req['images']) for req in value['requests']) else None
                wait_for(received,timeout=30)
                wait_for(lambda:'NEMOTERM_IMAGE_ACCEPTED' in api.request(endpoint,'text',seat),timeout=15)
                image=api.png_from_bmp(api.request(endpoint,'image',seat))
                (ROOT/f'research/agent-{args.client}-{name}.png').write_bytes(image)
                write_snapshot(control,dict(id=2,action='restore'))
                wait_for(lambda:read_snapshot(report).get('clipboard_restored'))
                for _ in range(2):
                    try:
                        if process.poll() is not None or not u.IsWindow(session['hwnd']):break
                        key(67,2)
                    except (OSError,EOFError):break
                    time.sleep(.2)
                assert process.wait(timeout=20)==0
                observed=read_snapshot(report)
                assert not observed['errors'],observed
                assert not observed['cleanup']['terminated_remaining'],observed['cleanup']
                observed['binding']=name
                observed['attachment_seconds']=attachment_seconds
                write_snapshot(ROOT/f'research/agent-{args.client}-{name}.json',observed)
                result['cases'].append(observed)
                print(args.client+' '+name+': exact generated image received; natural cleanup',flush=True)
            except Exception:
                result['failures'].append(dict(binding=name,error=traceback.format_exc()))
                try:
                    write_snapshot(control,dict(id=90,action='clipboard-probe'))
                    probe=wait_for(lambda:read_snapshot(report).get('clipboard_probe'),timeout=35)
                    print('Clipboard reader control:', json.dumps(probe), flush=True)
                except Exception as exc:
                    print('Clipboard reader control failed:', repr(exc), flush=True)
                try:
                    (case/'failure.txt').write_text(api.request(endpoint,'text',seat),encoding='utf-8')
                    (case/'failure.png').write_bytes(api.png_from_bmp(api.request(endpoint,'image',seat)))
                except Exception:pass
                print('Failure evidence: '+str(case),flush=True)
                # The other shortcut has a fresh process, profile and clipboard.
                # Run it as well; either original failure still fails this case.
            finally:
                if desk:
                    desk.restore();write_snapshot(case/'system-input.json',events)
                if process.poll() is None:
                    write_snapshot(control,dict(id=99,action='finish'))
                    try:process.wait(timeout=15)
                    except subprocess.TimeoutExpired:pass
                job.finish()
                write_snapshot(ROOT/f'research/agent-clipboard-{args.client}.json',result)
    result['completed']=not result['failures']
    write_snapshot(ROOT/f'research/agent-clipboard-{args.client}.json',result)
    print(json.dumps(result,indent=2))
    if result['failures']:raise SystemExit(1)


if __name__=='__main__':main()
