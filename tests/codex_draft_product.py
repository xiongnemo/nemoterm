"""Submit the untouched startup draft to a local provider and retain both sides."""
import argparse
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import traceback
from codex_image_reference import CLIENT, DRAFT, WARM
from fixture_io import read_snapshot, write_snapshot
from hosted_gesture_input import DesktopInput
from native_test_utils import wait_for
from owned_job import OwnedJob

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import nemoterm_debug as api


def trial(folder, args, source, i):
    product=Path(os.environ['NEMOTERM_TEST_EXE']).resolve(strict=True)
    transport='api' if i!=2 else 'physical-clipboard'
    rec=dict(transport=transport,phase=args.phase,renderer=args.renderer,expected=DRAFT,passed=False)
    desk=None
    with OwnedJob() as job:
        try:
            proc=job.spawn([sys.executable,str(ROOT/'tests/agent_clipboard_fixture.py'),'--client','codex','--client-exe',str(source),'--terminal',str(product),'--directory',str(folder),'--automation','--selection-renderer',args.renderer,'--draft-order','--font',os.environ['NEMOTERM_TEST_FONT']],creationflags=subprocess.CREATE_NO_WINDOW)
            report=lambda:read_snapshot(folder/'observed.json')
            ready=wait_for(lambda: report().get('pid'),timeout=30)
            inst=wait_for(lambda:next(iter(api.discover(ready)),None));seat,=inst['sessions']; assert seat['renderer']=={'gdi':0,'directx':2}[args.renderer]
            op=lambda name,data=b'':api.request(inst['endpoint'],name,seat['id'],data)
            key=lambda vk,m=0:op('key',struct.pack('<II',vk,m))
            if transport=='physical-clipboard':
                events={};desk=DesktopInput(ready,seat['window'],seat['hwnd'],events)
                # Stage generated text before observing the first prompt. No
                # clipboard mutation or second paste between gesture and Enter.
                write_snapshot(folder/'control.json',dict(id=1,action='draft-text'))
                wait_for(lambda: report().get('clipboard_action')==1)
            wait_for(lambda:'Ask Codex' in op('text'),timeout=60)
            if args.phase=='after-turn':
                op('paste',WARM);wait_for(lambda:WARM in op('text'));key(13)
                wait_for(lambda:'NEMOTERM_TEXT_ACCEPTED' in op('text') and any(WARM in r['text'] for r in report()['requests']),timeout=30)
            start=len(report()['requests']);raw=(folder/'client-output.log').read_bytes()
            (folder/'before-input.vt').write_bytes(raw);rec['idle_visible_before']=b'\x1b]7501;state=idle:app=codex' in raw
            if desk:desk.chord(0x11,0x10,86)
            else:op('paste',DRAFT)
            # No exact-text gate; a permutation or missing data must be submitted
            # unchanged. The same two-second observation window is used on the
            # independent consoles. Do not send another paste to repair a miss.
            time.sleep(2);screen=op('text');rec['marker_on_screen']=DRAFT in screen
            write_snapshot(folder/'before-submit.json',dict(text=screen));(folder/'before-submit.png').write_bytes(api.png_from_bmp(op('image')))
            (folder/'before-submit.vt').write_bytes((folder/'client-output.log').read_bytes())
            if desk:desk.chord(13)
            else:key(13)
            wait_for(lambda:any(r.get('draft_parts') for r in report()['requests'][start:]),timeout=30)
            rec['submitted']=[r['draft_parts'] for r in report()['requests'][start:] if r.get('draft_parts')]
            wait_for(lambda:'NEMOTERM_TEXT_ACCEPTED' in op('text'),timeout=15)
            for _ in range(2):
                if proc.poll() is not None:break
                try:key(67,2)
                except (EOFError,OSError):break
                time.sleep(.35)
            rec['exit_code']=proc.wait(timeout=15);state=report()
            rec.update(cleanup=state['cleanup'],terminal_sha256=state['terminal_sha256'],client_sha256=state['client_sha256'])
            assert rec['terminal_sha256']==hashlib.sha256(product.read_bytes()).hexdigest() and rec['client_sha256']==CLIENT
            assert not state['errors'] and rec['exit_code']==0 and not rec['cleanup']['terminated_remaining']
            assert rec['submitted']==[[DRAFT]] and rec['marker_on_screen'],rec
            rec['passed']=True
        except Exception:rec['error']=traceback.format_exc()
        finally:
            if desk:desk.restore();write_snapshot(folder/'system-input.json',events)
            if 'proc' in locals() and proc.poll() is None and folder.is_dir():
                write_snapshot(folder/'control.json',dict(id=99,action='finish'))
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:pass
            rec['controller_cleanup']=job.finish()
    return rec


def main():
    assert os.getenv('GITHUB_ACTIONS')=='true' and os.getenv('RUNNER_ENVIRONMENT')=='github-hosted'
    p=argparse.ArgumentParser();p.add_argument('--codex',type=Path,required=True);p.add_argument('--renderer',choices=('gdi','directx'),required=True);p.add_argument('--phase',choices=('first','after-turn'),required=True);args=p.parse_args()
    base=ROOT/'build/codex-draft-product';base.mkdir(parents=True,exist_ok=False);source=args.codex.resolve(strict=True)
    rows=[]
    for i in range(1,4):
        rows.append(trial(base/f'trial-{i}',args,source,i));write_snapshot(base/'summary.json',dict(trials=rows))
    return int(not all(r['passed'] for r in rows))


if __name__=='__main__':sys.exit(main())
