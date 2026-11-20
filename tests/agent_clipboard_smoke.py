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
from native_test_utils import c, u, w, wait_for
from owned_job import OwnedJob
from agent_ready_redraw import read_idle_redraw
from agent_image_receipt import chat_attachment, codex_first_submission

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import nemoterm_debug as api


def native_caption(host):
    u.GetWindowTextW.argtypes=[w.HWND,w.LPWSTR,c.c_int]
    text=c.create_unicode_buffer(512)
    u.GetWindowTextW(host,text,len(text))
    return text.value


def save_caption_pixels(host,path):
    from PIL import ImageGrab
    r=w.RECT()
    u.GetWindowRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
    assert u.GetWindowRect(host,c.byref(r))
    box=(r.left,r.top,r.right,min(r.bottom,r.top+96))
    ImageGrab.grab(bbox=box,all_screens=True).save(path)
    return box


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client',choices=('codex','opencode'),required=True)
    parser.add_argument('--client-exe',required=True)
    parser.add_argument('--terminal',default=os.environ.get('NEMOTERM_TEST_EXE',str(ROOT/'dist/nemoterm.exe')))
    parser.add_argument('--font',default=os.environ.get('NEMOTERM_TEST_FONT','SarasaTermSC Nerd Light'))
    parser.add_argument('--system-input', action='store_true')
    parser.add_argument('--after-client-idle',action='store_true',help='Also require Codex to report idle and redraw the marker after startup queries')
    parser.add_argument('--submit-first-miss',action='store_true',help='Retain the missing attachment failure and submit that unchanged early draft once to the loopback service')
    parser.add_argument('--observe-first-miss', action='store_true', help='Keep the failed startup gesture and separately observe one subsequent user action in that same session')
    parser.add_argument('--after-window-caption',action='store_true',help='Physically paste when the real window displays the fixture project name, without waiting for a VT status or redraw')
    parser.add_argument('--witness-bitmap',action='store_true',help='Observe first Windows request for the generated bitmap with a delayed-rendering owner')
    parser.add_argument('--opencode-title',choices=('default','disabled'))
    parser.add_argument('--mixed-bitmap', action='store_true', help='Publish an empty Unicode text alternative alongside the generated DIB')
    parser.add_argument('--image-file', action='store_true', help='Paste a real copied PNG file (CF_HDROP only) instead of a clipboard bitmap')
    parser.add_argument('--binding',choices=('ctrl-v','ctrl-shift-v'))
    args=parser.parse_args()
    folder=Path(tempfile.mkdtemp(prefix='agent-image-',dir=ROOT/'build'))
    result=dict(client=args.client,cases=[],live_model=False,tool_responses=False,font=args.font)
    if args.witness_bitmap:
        assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted' and args.client=='codex' and not args.image_file and not args.after_window_caption
        result['delayed_bitmap_diagnostic']=True
    if args.opencode_title:assert args.client=='opencode' and args.mixed_bitmap
    if args.mixed_bitmap:assert (args.after_client_idle or args.client=='opencode') and not args.image_file and not args.witness_bitmap
    if args.image_file:assert args.client=='codex' and not args.after_window_caption and not args.observe_first_miss
    if args.after_window_caption:assert args.client=='codex' and args.system_input and not args.after_client_idle and not args.observe_first_miss
    if args.after_client_idle:assert args.client=='codex'
    if args.submit_first_miss:
        assert args.client=='codex' and not any((args.observe_first_miss,args.after_client_idle,args.image_file,
                                                args.mixed_bitmap,args.after_window_caption,args.witness_bitmap))
    if args.observe_first_miss:assert args.client=='codex' and not args.after_client_idle
    result.update(clipboard_format='CF_HDROP' if args.image_file else 'empty CF_UNICODETEXT + CF_DIB' if args.mixed_bitmap else 'CF_DIB',system_input=args.system_input,after_client_idle=args.after_client_idle,after_window_caption=args.after_window_caption,failures=[])
    for name,mods in [('ctrl-v',2),('ctrl-shift-v',3)]:
        if args.binding and args.binding!=name:continue
        case=folder/name;report=case/'observed.json';control=case/'control.json'
        with OwnedJob() as job, (folder/(name+'.log')).open('w',encoding='utf-8') as log:
            process=job.spawn([sys.executable,str(ROOT/'tests/agent_clipboard_fixture.py'),
                '--client',args.client,'--client-exe',str(Path(args.client_exe).resolve()),
                '--terminal',str(Path(args.terminal).resolve()),'--directory',str(case),
                '--automation','--font',args.font,*(['--witness-bitmap'] if args.witness_bitmap else []),
                *(['--image-title',args.opencode_title] if args.opencode_title else [])],stdout=log,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
            desk=None;events={};followup=None;missed=None
            try:
                observed=wait_for(lambda:read_snapshot(report),timeout=30)
                instance=wait_for(lambda:next(iter(api.discover(observed['pid'])),None),timeout=20)
                endpoint=instance['endpoint'];session,=instance['sessions'];seat=session['id']
                if args.after_window_caption:
                    caption_record=dict(host=session['window'],initial=native_caption(session['window']),expected='work')
                    write_snapshot(case/'caption.json',caption_record)
                if args.system_input:
                    from hosted_gesture_input import DesktopInput
                    desk=DesktopInput(observed['pid'],session['window'],session['hwnd'],events)
                gesture_clock=[]
                def key(vk,mods):
                    stamp=time.perf_counter_ns() if args.witness_bitmap and vk==86 else None
                    if desk:
                        keys={0:(),2:(0x11,),3:(0x11,0x10)}[mods];desk.chord(*keys,vk)
                    else:api.request(endpoint,'key',seat,struct.pack('<II',vk,mods))
                    if stamp is not None:
                        gesture_clock.append(dict(start_ns=stamp,end_ns=time.perf_counter_ns()))
                        write_snapshot(case/'bitmap-gestures.json',gesture_clock)
                if args.image_file:
                    write_snapshot(control,dict(id=1,action='image-file'))
                    file_state=wait_for(lambda:read_snapshot(report).get('file_clipboard'))
                    write_snapshot(case/'file-clipboard.json',file_state)
                ready='Ask Codex' if args.client=='codex' else 'Ask anything'
                wait_for(lambda:ready in api.request(endpoint,'text',seat),timeout=60)
                marker='NEMOTERM_'+args.client.upper()+'_IMAGE_'+name.upper().replace('-','_')
                # A painted startup prompt is not an input-consumption ack.
                # Observe the application consume this prompt before asking
                # its asynchronous clipboard reader to attach an image.
                api.request(endpoint,'paste',seat,marker)
                wait_for(lambda:marker in api.request(endpoint,'text',seat),timeout=20)
                trace=case/'client-output.log'
                def idle_redraw():
                    if not trace.is_file():return False
                    proof=read_idle_redraw(trace.read_bytes(),marker,lambda:api.request(endpoint,'text',seat))
                    if proof:write_snapshot(case/'idle-redraw.json',proof)
                    return proof
                if args.after_client_idle:wait_for(idle_redraw,timeout=60)
                if not args.image_file:
                    write_snapshot(control,dict(id=1,action='mixed-bitmap' if args.mixed_bitmap else 'bitmap'))
                    wait_for(lambda:read_snapshot(report).get('clipboard_action')==1)
                # The caption phase gates only on the foreground window a user sees.
                # Do not read the VT trace, capture pixels or write files between the
                # first matching caption sample and the actual physical key chord.
                if args.after_window_caption:
                    def matching_caption():
                        desk.target()
                        title=native_caption(desk.host)
                        return (title,time.monotonic()) if title==caption_record['expected'] else None
                    title,seen=wait_for(matching_caption,timeout=60)
                    attachment_started=time.monotonic();key(86,mods)
                    sent=time.monotonic()
                    desk.target()
                    caption_record.update(matched=title,key_started_ms=(attachment_started-seen)*1000,
                        key_completed_ms=(sent-seen)*1000,after_key=native_caption(desk.host),
                        crop=save_caption_pixels(desk.host,case/'caption-after-key.png'))
                    write_snapshot(case/'caption.json',caption_record)
                before=trace.read_bytes() if trace.is_file() else b''
                boundary='after-caption-gesture' if args.after_window_caption else 'at-paste'
                (case/(boundary+'.vt')).write_bytes(before)
                evidence=dict(marker=marker,system=bool(desk),binding=name,session=session,
                    bytes=len(before),sha256=hashlib.sha256(before).hexdigest())
                idle_key='idle_in_post_gesture_trace' if args.after_window_caption else 'idle_before'
                evidence[idle_key]=b'\x1b]7501;state=idle:app=codex' in before
                write_snapshot(case/(boundary+'.json'),evidence)
                if not args.after_window_caption:
                    attachment_started=time.monotonic()
                    key(86,mods)
                # OpenCode launches Windows PowerShell/WinForms to read images.
                # A fresh hosted runner exceeded 20 s, then painted the exact
                # attachment while a separate reader control also succeeded.
                has_attachment=lambda:'[Image' in api.request(endpoint,'text',seat)
                try:wait_for(has_attachment,timeout=60 if args.client=='opencode' else 20)
                except AssertionError as miss:
                    if str(miss)!='Timed out waiting for native fixture':raise
                    if args.submit_first_miss:
                        # This deadline is still a failure, irrespective of what the server sees later.
                        result['failures'].append(dict(binding=name,stage='first-attachment',error=traceback.format_exc()))
                        missed=dict(binding=name,idle_before=evidence['idle_before'],enter_sent=False,
                                    terminal_sha256=observed['terminal_sha256'],client_sha256=observed['client_sha256'],
                                    outcome='no-receipt')
                        result.setdefault('submitted_after_miss',[]).append(missed)
                        draft=api.request(endpoint,'text',seat)
                        missed['attachment_visible_on_next_read']='[Image' in draft
                        (case/'first-miss.txt').write_text(draft,encoding='utf-8')
                        (case/'first-miss.png').write_bytes(api.png_from_bmp(api.request(endpoint,'image',seat)))
                        assert marker in draft and not any(marker in req['text'] for req in read_snapshot(report)['requests'])
                    elif args.observe_first_miss:
                        # The original gate remains red even if the same draft can recover.
                        result['failures'].append(dict(binding=name,stage='first-attachment',error=traceback.format_exc()))
                        followup=dict(binding=name,pid=observed['pid'],session=seat,second_gesture=False,completed=False)
                        result.setdefault('same_draft_observations',[]).append(followup)
                        (case/'first-miss.png').write_bytes(api.png_from_bmp(api.request(endpoint,'image',seat)))
                        wait_for(idle_redraw,timeout=60)
                        draft=api.request(endpoint,'text',seat);(case/'before-followup.txt').write_text(draft,encoding='utf-8')
                        assert marker in draft and process.poll() is None and not any(marker in req['text'] for req in read_snapshot(report)['requests'])
                        (case/'before-followup.vt').write_bytes(trace.read_bytes())
                        if '[Image' not in draft:
                            followup['second_gesture']=True;followup['seconds_after_first']=time.monotonic()-attachment_started
                            key(86,mods);wait_for(has_attachment,timeout=20)
                        else:followup['late_first_attachment']=True
                    else:raise

                attachment_seconds=time.monotonic()-attachment_started
                time.sleep(.2)
                key(13,0)
                if missed is not None: missed['enter_sent']=True
                def received():
                    value=read_snapshot(report)
                    if missed is not None:
                        return value if value and any(r['path']=='/v1/responses' and marker in r['text'] for r in value['requests']) else None
                    return value if value and any(marker in req['text'] and any(
                        im.get('generated_pixels_match') for im in req['images']) for req in value['requests']) else None
                first=wait_for(received,timeout=30)
                reply='NEMOTERM_IMAGE_ACCEPTED'
                if missed is not None:
                    missed['requests']=first['requests']; missed['outcome']=codex_first_submission(first['requests'],name)
                    if missed['outcome']=='text-only':reply='NEMOTERM_TEXT_ACCEPTED'
                wait_for(lambda:reply in api.request(endpoint,'text',seat),timeout=15)
                if missed is not None:
                    write_snapshot(control,dict(id=90,action='clipboard-probe'))
                    missed['clipboard_probe']=wait_for(lambda:read_snapshot(report).get('clipboard_probe'),timeout=35)
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
                if missed is None: observed['attachment_seconds']=attachment_seconds
                else: observed['seconds_until_attachment_deadline']=attachment_seconds
                if args.after_window_caption:observed['caption']=caption_record
                write_snapshot(ROOT/f'research/agent-{args.client}-{name}.json',observed)
                if missed is not None:
                    missed['requests']=observed['requests'];missed['outcome']=codex_first_submission(observed['requests'],name)
                    missed['clipboard_restored']=observed['clipboard_restored'];missed['cleanup']=observed['cleanup']
                    continue
                if args.witness_bitmap:
                    witness=read_snapshot(case/'bitmap-requests.json')
                    hits=[e for e in witness['events'] if e['reason']=='WM_RENDERFORMAT' and e['supplied']]
                    assert not witness['errors'] and len(hits)==1 and witness['published_ns']<=gesture_clock[0]['start_ns']<=hits[0]['ns']<=hits[0]['supplied_ns'],(witness,gesture_clock)
                if args.image_file or args.mixed_bitmap or args.after_window_caption or args.witness_bitmap or followup is not None:
                    relevant=[r for r in observed['requests'] if marker in r['text'] and r['images']]
                    if args.opencode_title=='disabled':
                        assert all(r['has_opencode_title_instruction'] is False for r in relevant),relevant
                    assert len(relevant)==1 and len(relevant[0]['images'])==1 and relevant[0]['images'][0]['generated_pixels_match'],relevant
                observed['chat_attachment']=chat_attachment(observed['requests'],args.client,name)
                if followup is not None:
                    followup.update(completed=True,observation=observed)
                else: result['cases'].append(observed)
                print(args.client+' '+name+': exact generated image received; natural cleanup',flush=True)
            except Exception:
                result['failures'].append(dict(binding=name,error=traceback.format_exc()))
                try:
                    if args.image_file:
                        draft=api.request(endpoint,'text',seat)
                        write_snapshot(case/'file-paste-failure.json',dict(
                            path_basename_visible='clipboard 图片 sample.png' in draft,
                            attachment_visible='[Image' in draft,requests=read_snapshot(report)['requests']))
                    elif not args.witness_bitmap:
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
