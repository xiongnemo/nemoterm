"""Compare the text visible at a real Shift gesture with the Windows clipboard."""
from collections import Counter
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from clipboard_test_utils import SavedClipboard, clipboard_text, set_clipboard
from hosted_gesture_input import DesktopInput
from native_test_utils import c, w, u, memory_sample, root, find_window, terminal_host, wait_for, capture_result
from fixture_io import read_snapshot, write_snapshot
from owned_job import OwnedJob
from presented_window_capture import PresentedWindowCapture
from protocol_oracle_window import saved_profile

CSI = '\x1b['
DSR, ACK = CSI+'5n', b'\x1b[0n'
OLD, NEW = '中文', '明月'
QUERIES = ''.join(CSI+f'?{m}$p' for m in (2026, 1002, 1006))


def run(engine, output, paste):
    assert os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted' and os.environ.get('GITHUB_ACTIONS') == 'true'
    exe = Path(os.environ['NEMOTERM_TEST_EXE']).resolve()
    font = os.environ['NEMOTERM_TEST_FONT']
    output.update(exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), font=font, cases=[])
    def draw(row, text):
        return CSI+f'{row+1};4H'+text
    def marker(row, current):
        # The colour chip outside the selection identifies its backing frame even when highlighted.
        return CSI+f'{row+1};12H'+CSI+'48;2;'+('180;32;16' if current==OLD else '16;48;180')+'m   '+CSI+'0m'
    def scene(row, current):return draw(row,current)+marker(row,current)
    def mode_reply(frozen):
        return (CSI+f'?2026;{1 if frozen else 2}$y'+CSI+'?1002;1$y'+CSI+'?1006;1$y').encode()
    settings=dict(NemoRenderer=engine-1, WarnOnClose=0, NemoOSC52Write=1, NemoOSC52Read=1)
    if paste: settings['RightClickCopyAndPaste']=1
    with tempfile.TemporaryDirectory() as folder, OwnedJob() as job, saved_profile(settings) as profile:
        report, control = (Path(folder)/f for f in ('report','control'))
        proc = job.spawn([str(exe), *profile, '--tabs','--font',font,'--cols','80','--rows','24','-e', sys.executable,
                          str(root/'tests/mouse_fixture.py'),str(report),str(control),'150'],
                         env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1',NEMOTERM_TEST_INPUT_CP='65001',NEMOTERM_TEST_WIDE_INPUT='1'),creationflags=subprocess.CREATE_NO_WINDOW)
        hwnd = wait_for(lambda: find_window(proc.pid)); host=terminal_host(hwnd); assert host != hwnd
        u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
        output['actual_renderer']=u.GetPropW(hwnd,'NemotermRenderer'); assert output['actual_renderer']==engine
        saved=SavedClipboard(hwnd); desktop=cap=None
        try:
            desktop=DesktopInput(proc.pid,host,hwnd,output.setdefault('desktop',{})); cap=PresentedWindowCapture(proc.pid,hwnd,engine==3,raise_window=False)
            cap.wait_for_initial_geometry(); rect=w.RECT(); assert u.GetClientRect(hwnd,c.byref(rect))
            width,height=rect.right,rect.bottom; cw,ch=(width-2)//80,(height-2)//24
            output['geometry']=[width,height,cw,ch]
            def point(x,y): desktop.point(1+x*cw+cw//2,1+y*ch+ch//2)
            def snapshot():
                v=read_snapshot(report); assert proc.poll() is None and not v.get('error'),v
                return v
            wait_for(lambda: (v:=snapshot()).get('columns')==80 and v.get('rows')==24)
            def phase(name, sequence):
                req=dict(phase=name, sequence=sequence+DSR, preserve_mouse=True)
                write_snapshot(control,req)
                v=wait_for(lambda: s if (s:=snapshot()).get('phase')==name and bytes.fromhex(s['hex']).endswith(ACK) else None)
                return req, bytes.fromhex(v['hex'])
            def drain(req):
                write_snapshot(control,dict(req,input_barrier='after-gesture'))
                return bytes.fromhex(wait_for(lambda: s if (s:=snapshot()).get('phase')==req['phase'] and s.get('input_barrier')=='after-gesture' else None)['hex'])
            def sample():
                bmp=cap.capture(); assert struct.unpack_from('<ii',bmp,18)==(width,-height)
                return bmp[54:]
            def tile(frame,x,y):
                return b''.join(frame[(width*j+1+x*cw)*4:(width*j+1+(x+1)*cw)*4] for j in range(1+y*ch,1+(y+1)*ch))
            def glyphs(frame,y):return b''.join(tile(frame,x,y) for x in range(3,7))
            def chip(frame,y):return tuple(tile(frame,12,y)[:3][::-1])
            def glyph_shape(frame,y):
                data=glyphs(frame,y); colours=[data[i:i+3] for i in range(0,len(data),4)]
                bg=Counter(colours).most_common(1)[0][0]
                return bytes(c!=bg for c in colours)
            def drag(y,held=None,block=False):
                point(3,y);desktop.event(0x10,True)
                if block:desktop.event(0x11,True)
                desktop.event(None,True)
                try:
                    wait_for(lambda:desktop.state().capture==hwnd);point(6,y)
                    if held:held()
                finally:
                    desktop.event(None,False);wait_for(lambda:desktop.state().capture!=hwnd)
                    if block:desktop.event(0x11,False)
                    desktop.event(0x10,False)
            cases=(
                ('live-old',False,False,'key',OLD),('live-new',False,False,'key',NEW),
                ('press-frozen',False,True,'key',OLD),('copy-frozen',True,True,'key',OLD),('right-frozen',True,True,'right',OLD),
                ('copy-primary',True,True,'key',OLD),('right-primary',True,True,'right',OLD),
                ('press-slow',False,True,'key',OLD),('press-rectangle',False,True,'key',OLD),
                ('press-neighbour',False,True,'key',OLD),('press-neighbour-rectangle',False,True,'key',OLD))
            if paste:cases=tuple(c for c in cases if c[3]=='right')
            for index,(case,preselect,freeze,action,initial) in enumerate(cases):
                primary=case.endswith('primary')
                neighbour=case.startswith('press-neighbour')
                if paste:case+='-paste'
                y=4+2*(index%7); row=dict(case=case,expected=initial);output['cases'].append(row)
                req,raw=phase(case+'-start','\x1bc'+CSI+'?25l'+CSI+'?1002;1006h'+draw(18,OLD)+draw(20,NEW)+scene(y,initial)+QUERIES)
                assert raw==mode_reply(False)+ACK,raw
                ref=18 if initial==OLD else 20; oldchip=(180,32,16); newchip=(16,48,180)
                before=wait_for(lambda: f if chip(f:=sample(),y)==(oldchip if initial==OLD else newchip) and glyphs(f,y)==glyphs(f,ref) and glyphs(f,18)!=glyphs(f,20) else None)
                set_clipboard(hwnd,'untouched:'+case)
                # Position the pointer before freezing. No input filter or renderer hook is installed.
                point(3,y)
                if preselect:
                    drag(y)
                    def highlighted():
                        frame=sample()
                        return frame if all(tile(frame,x,y)!=tile(frame,x,ref) for x in range(3,7)) else None
                    before=wait_for(highlighted)
                seq=u.GetClipboardSequenceNumber(); t0=time.perf_counter_ns()
                primary_set='\x1b]52;p;TkVX\x07' if primary else ''
                primary_read='\x1b]52;p;?\x07' if primary else ''
                prefix=primary_set.encode()+mode_reply(freeze)
                update=marker(y,NEW) if neighbour else scene(y,NEW)
                req,raw=phase(case+'-gesture',(CSI+'?2026h'+update if freeze else '')+primary_set+primary_read+QUERIES)
                assert raw==prefix+ACK,raw
                observed=sample(); row['pre_gesture_ms']=(time.perf_counter_ns()-t0)/1e6
                row['pre_gesture_same_cells']=glyphs(observed,y)==glyphs(before,y);row['pre_gesture_chip']=chip(observed,y)
                held_frames={}
                def inspect_held():
                    def changed(frame):return [x for x in range(2,9) if tile(observed,x,y)!=tile(frame,x,y)]
                    def visible_highlight():
                        frame=sample(); held_frames['held']=frame
                        return frame if changed(frame)==[3,4,5,6] else None
                    # Record even a wrong frame; its glyph shape and chip determine pass/fail.
                    until=time.monotonic()+.40
                    while not visible_highlight() and time.monotonic()<until:time.sleep(.01)
                    row['first_highlight_ms']=(time.perf_counter_ns()-t0)/1e6
                    if case=='press-slow':
                        time.sleep(1.15);held_frames['held-over-deadline']=sample()
                    row['held_checks']={label:dict(changed=changed(f),chip=chip(f,y),
                        old_glyphs=glyph_shape(f,y)==glyph_shape(observed,18),new_glyphs=glyph_shape(f,y)==glyph_shape(observed,20),
                        captured=desktop.state().capture==hwnd) for label,f in held_frames.items()}
                    row['held_memory']=memory_sample(proc._handle)
                if not preselect:drag(y,inspect_held if freeze else None,block=case.endswith('rectangle'))
                if action=='key':desktop.chord(0x11,0x10,ord('C'))
                else:desktop.event('right',True);desktop.event('right',False)
                row['gesture_sent_ms']=(time.perf_counter_ns()-t0)/1e6
                raw=drain(req); row['gesture_wire']=raw.hex(); row['fresh_clipboard']=u.GetClipboardSequenceNumber()!=seq
                row['copied']=clipboard_text(hwnd); after=sample();row['after_chip']=chip(after,y)
                _,post=phase(case+'-after',QUERIES);row['post_mode_wire']=post.hex()
                row['sample_end_ms']=(time.perf_counter_ns()-t0)/1e6
                _,end=phase(case+'-release',CSI+'?2026l'+QUERIES);assert end==mode_reply(False)+ACK
                if freeze:wait_for(lambda:chip(sample(),y)==newchip)
                for label,pixels in (('before',before),('gesture',observed),('after',after),*held_frames.items()):
                    capture_result(width,height,pixels,f'sync-select-{engine}-{case}-{label}.png')
                row['passed']=(row['pre_gesture_same_cells'] and tuple(row['pre_gesture_chip'])==(oldchip if initial==OLD else newchip) and
                               (not freeze or (1120<row['sample_end_ms'] if case=='press-slow' else row['sample_end_ms']<1000)) and raw==prefix+ACK+(initial.encode() if paste else b'')+ACK and
                               row['fresh_clipboard'] and row['copied']==initial)
                if held_frames:
                    row['passed'] &= (row['first_highlight_ms']<1000 and post==mode_reply(False)+ACK and
                                      all(h['changed']==[3,4,5,6] and h['old_glyphs'] and not h['new_glyphs'] and
                                          h['captured'] and h['chip']==oldchip for h in row['held_checks'].values()) and
                                      row['held_memory']['private_ws'] < (20_000_000 if engine==1 else 30_000_000))
                if neighbour or case=='press-frozen':
                    # Repaint has presented the hidden frame. Inspect the selection and right click again,
                    # with a new clipboard sentinel: shortcuts can still use a previous primary selection.
                    committed=sample(); ref_y=18 if neighbour else 20
                    capture_result(width,height,committed,f'sync-select-{engine}-{case}-committed.png')
                    marked=[x for x in range(3,7) if tile(committed,x,y)!=tile(committed,x,ref_y)]
                    set_clipboard(hwnd,'committed:'+case);seq=u.GetClipboardSequenceNumber()
                    point(6,y);req,_=phase(case+'-committed-right',QUERIES);desktop.chord('right');wire=drain(req)
                    fresh=u.GetClipboardSequenceNumber()!=seq;copied=clipboard_text(hwnd)
                    mouse=(CSI+f'<2;7;{y+1}M'+CSI+f'<2;7;{y+1}m').encode()
                    row['commit_check']=dict(wire=wire.hex(),marked=marked,clipboard=copied,fresh=fresh)
                    row['passed'] &= (wire==mode_reply(False)+ACK+(b'' if neighbour else mouse)+ACK and fresh==neighbour and
                                      copied==(OLD if neighbour else 'committed:'+case) and marked==([3,4,5,6] if neighbour else []) and
                                      glyph_shape(committed,y)==glyph_shape(committed,ref_y))
                if freeze and preselect:
                    # The following frame no longer highlights the text. Both right-button edges must now reach the application.
                    point(6,y); req,raw=phase(case+'-released-right',QUERIES); seq=u.GetClipboardSequenceNumber()
                    assert raw==mode_reply(False)+ACK
                    desktop.chord('right'); wire=drain(req); row['committed_right_wire']=wire.hex()
                    mouse=(CSI+f'<2;7;{y+1}M'+CSI+f'<2;7;{y+1}m').encode()
                    row['passed'] &= wire==mode_reply(False)+ACK+mouse+ACK and u.GetClipboardSequenceNumber()==seq
        finally:
            if cap:output['capture']=cap.close()
            if desktop:desktop.restore()
            saved.restore();write_snapshot(control,dict(stop=True));output['returncode']=proc.wait(timeout=10)
        output['cleanup']=job.finish(); assert output['returncode']==0 and not output['cleanup']['terminated_remaining']
    assert all(r['passed'] for r in output['cases']),[(r['case'],r['copied'],r['pre_gesture_chip'],r['sample_end_ms']) for r in output['cases'] if not r['passed']]


if __name__=='__main__':
    engine={'gdi':1,'directx':3}[sys.argv[1]]; result={}; paste='--paste' in sys.argv[2:]
    try:run(engine,result,paste)
    except BaseException as exc:
        result['error']=repr(exc);raise
    finally:(root/'research'/('sync-select-%d%s.json'%(engine,'-paste' if paste else ''))).write_text(json.dumps(result,indent=2),encoding='utf8')
