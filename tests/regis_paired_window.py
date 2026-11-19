"""Replay one immutable, whole-write XTerm prefix on one fresh presented GDI window."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
from zipfile import ZipFile
from PIL import Image, ImageChops
from regis_window_smoke import main, CSI, u, w, c, api, BORDER, COLS, ROWS
from native_test_utils import wait_for
from fixture_io import write_snapshot

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = 'd2ffea585f6477c2f71598107b7df74df8ebbc0e5f7c6bd1f0a5b13c4145604c'
sha = lambda b: hashlib.sha256(b).hexdigest()


def resize_grid(ev):
    # The history used X11's 6x13 fixed cells. Resize only this standalone
    # HWND with the product's normal "change font size on resize" setting.
    s = ev['session']; hwnd = s['hwnd']; assert s['window'] == hwnd and ev['actual_renderer'] == 0
    outer, client = w.RECT(), w.RECT()
    assert u.GetWindowRect(hwnd, c.byref(outer)) and u.GetClientRect(hwnd, c.byref(client))
    width, height = COLS*6 + 2*BORDER, ROWS*13 + 2*BORDER
    ev['initial_client'] = [client.right, client.bottom]
    assert u.SetWindowPos(hwnd, None, 0, 0, width+outer.right-outer.left-client.right,
                          height+outer.bottom-outer.top-client.bottom, 0x16)  # no move, Z-order or focus
    def sized():
        assert u.GetClientRect(hwnd, c.byref(client))
        return (client.right,client.bottom) == (width,height)
    wait_for(sized)


def mismatches(a,b):
    assert a.size == b.size == (160,120)
    r,g,blue = ImageChops.difference(a,b).split()
    delta = ImageChops.lighter(ImageChops.lighter(r,g),blue)
    return dict(pixels=160*120-delta.histogram()[0], box=delta.getbbox())


def run(tag):
    source=(ROOT/'research/regis-first-expose-captures.zip').read_bytes(); assert sha(source)==ARCHIVE
    ev={}; comparisons={}; historical_failures=[]; capture_failures=[]
    with ZipFile(io.BytesIO(source)) as ref:
        facts=json.loads(ref.read('reference/observations.json'))
        scene,last=facts['targets'][tag]; upstream=facts['cases'][tag]['whole']
        assert facts['completed'] and upstream['completed'] and upstream['cell_pixels']==[6,13]
        assert not facts['control_failures'] and not facts['transport_mismatches']
        assert len(upstream['steps']) == last+1 and all('repaint' not in s for s in upstream['steps'][:-1])
        final=upstream['steps'][-1]; assert final['repaint_barrier_hex']=='1b5b306e'
        prefix='reference/observations/'+tag+'-whole/'
        def upstream_image(record):
            image=Image.open(io.BytesIO(ref.read(prefix+record['file']))).convert('RGB')
            assert sha(image.tobytes())==record['rgb_sha256']
            crop=image.crop((2,2,162,122))
            if 'graphic_crop_rgb_sha256' in record: assert sha(crop.tobytes())==record['graphic_crop_rgb_sha256']
            return crop
        def exercise(phase,block):
            assert ev['cell_pixels']==[6,13] and ev['image_size']==[242,158],ev['cell_pixels']
            capture_dir=Path(ev['folder']); text_control=scene=='control-text'
            def frame(label,wire,reply,reference,comparison_required=True):
                samples=[]; memo={}; first=time.perf_counter_ns(); last_frame=[None]
                def consume(record,width,bgra):
                    image=Image.frombytes('RGB',(width,len(bgra)//(4*width)),bgra,'raw','BGRX')
                    crop=image.crop((BORDER,BORDER,BORDER+160,BORDER+120)); digest=sha(crop.tobytes())
                    samples.append(dict(ms=(time.perf_counter_ns()-first)/1e6,sha256=digest))
                    if digest not in memo:
                        crop.save(capture_dir/(label+'-'+digest[:16]+'.png'))
                        memo[digest]=mismatches(crop,reference)
                    last_frame[0]=crop
                    return True  # fixed observation window, independent of any expected pixels
                phase(label,wire,[],expected_reply=reply,stable_seconds=.25,pixel_check=consume)
                digest=samples[-1]['sha256']; i=len(samples)-1
                while i and samples[i-1]['sha256']==digest: i-=1
                stable_ms=samples[-1]['ms']-samples[i]['ms']
                row=comparisons[label]=dict(samples=samples,reference_sha256=sha(reference.tobytes()),
                    samples_vs_reference=memo,last_sha256=digest,last_difference=memo[digest],last_stable_ms=stable_ms,
                    check_literal_pixels=comparison_required)
                if len(samples)<2 or stable_ms<80: capture_failures.append(label+': unsettled')
                if comparison_required and row['last_difference']['pixels']: historical_failures.append(label)
                return last_frame[0]
            initial=upstream_image(upstream['initial_frame'])
            frame('geometry',CSI+'?25l'+CSI+'16t',b'\x1b[6;13;6t',initial)
            for i,step in enumerate(upstream['steps']):
                wire=bytes.fromhex(step['sequence_hex']); raw_reply=bytes.fromhex(step['reply_hex'])
                assert bytes.fromhex(step['wire_with_barrier_hex']) == wire+b'\x1b[5n'
                assert bytes.fromhex(step['reply_with_barrier_hex']) == raw_reply+b'\x1b[0n'
                before=frame('step-'+str(i),wire.decode('ascii'),raw_reply,upstream_image(step['frame']),not text_control)
            assert u.RedrawWindow(ev['session']['hwnd'],None,None,0x185)
            after=frame('exposed','',b'',upstream_image(final['repaint']),not text_control)
            # Different fonts: check a real visible glyph run and its stability,
            # not equality to the X11 fixed-font glyph shapes.
            if text_control:
                cells=api.request(ev['endpoint'],'text',ev['session']['id']); occupied=before.getbbox()
                passed=bool(occupied and occupied[2]<=7*6 and occupied[3]<=13 and 'CONTROL' in cells and
                            before.tobytes()==after.tobytes())
                if not passed: capture_failures.append('text control')
            write_snapshot(capture_dir/'paired.json',dict(tag=tag,scene=scene,step=last,archive_sha256=ARCHIVE,
                transport='whole',font=os.environ['NEMOTERM_TEST_FONT'],cells=ev['cell_pixels'],
                product_sha256=ev['executable_sha256'],reference_exe_sha256=facts['executable_sha256'],
                frames=comparisons,before_vs_after=mismatches(before,after),
                historical_pixel_failures=historical_failures,capture_failures=capture_failures))
        assert '--presented-gdi' in sys.argv
        main(exercise,suite_name='regis-window-pair-'+tag, before_exercise=ev.update,prepare_window=resize_grid,
             font=os.environ['NEMOTERM_TEST_FONT'],profile_values=dict(NemoTabs=0,LockSize=2))
    # A mismatch must not prevent subsequent frame capture or natural cleanup.
    if historical_failures or capture_failures: sys.exit(f'{tag}: historical pixels {historical_failures}, capture {capture_failures}')


if __name__=='__main__': run(sys.argv.pop(1))
