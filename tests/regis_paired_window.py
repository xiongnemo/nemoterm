"""Replay one immutable XTerm prefix on a fresh visible GDI or DirectX window."""
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
BANK_ARCHIVE = '2330a3808f2a1b2945eef5931328665ec72b8fda387ba6f22a9f82c5d8c86943'
MOTION_ARCHIVE = '2da558cf2246e03091861a2450969c6c5c1808a2b5416b358a5c2fdbd583a162'
sha = lambda b: hashlib.sha256(b).hexdigest()


def resize_grid(ev):
    # The history used X11's 6x13 fixed cells. Resize only this standalone
    # HWND with the product's normal "change font size on resize" setting.
    s = ev['session']; hwnd = s['hwnd']; assert s['window'] == hwnd and ev['actual_renderer'] == {'gdi':0,'directx':2}[ev['requested_renderer']]
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
    write_mode=os.environ.get('NEMOTERM_REGIS_WRITE_MODE')
    tx=write_mode or 'whole'
    assert tx in ('whole','bytewise')
    bank=tag.startswith('bank-start-')
    motion=tag.startswith('text-motion-')
    archive_hash=MOTION_ARCHIVE if motion else BANK_ARCHIVE if bank else ARCHIVE
    filename='regis-bank-start-xterm.zip' if bank else 'regis-first-expose-captures.zip'
    if motion: filename='regis-text-motion-xterm.zip'
    source=(ROOT/'testdata/upstream'/filename).read_bytes(); assert sha(source)==archive_hash
    ev={}; comparisons={}; historical_failures=[]; capture_failures=[]; reply_failures=[]
    with ZipFile(io.BytesIO(source)) as ref:
        facts=json.loads(ref.read('reference/observations.json'))
        scene,last=(tag,0) if bank else facts['targets'][tag]
        upstream=facts['cases'][tag][tx]
        if motion:
            from regis_text_motion import scenes
            assert [s['sequence_hex'] for s in upstream['steps']]==scenes()[tag]
        if bank:
            from shared_bank_start_cases import bank_starts
            wire,=bank_starts()[tag.removeprefix('bank-start-')]
            assert upstream['steps'][0]['sequence_hex']==wire.encode('ascii').hex()
            assert facts['repaint'] and not facts['first_expose']
        assert facts['completed'] and upstream['completed'] and upstream['cell_pixels']==[6,13]
        assert not facts['control_failures'] and not facts['transport_mismatches']
        assert len(upstream['steps']) == last+1 and all('repaint' not in s for s in upstream['steps'][:-1])
        final=upstream['steps'][-1]; assert final['repaint_barrier_hex']=='1b5b306e'
        prefix='reference/observations/'+tag+'-'+tx+'/'
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
                phase(label,wire,[],expected_reply=None if motion else reply,stable_seconds=.25,pixel_check=consume)
                digest=samples[-1]['sha256']; i=len(samples)-1
                while i and samples[i-1]['sha256']==digest: i-=1
                stable_ms=samples[-1]['ms']-samples[i]['ms']
                row=comparisons[label]=dict(samples=samples,reference_sha256=sha(reference.tobytes()),
                    samples_vs_reference=memo,last_sha256=digest,last_difference=memo[digest],last_stable_ms=stable_ms,
                    check_literal_pixels=comparison_required)
                if motion:
                    expected=(reply+b'\x1b[0n').hex()
                    actual=ev['checks'][-1]['reply_hex']
                    row.update(expected_reply_hex=expected,actual_reply_hex=actual)
                    if actual!=expected: reply_failures.append(label)
                if bank:
                    def stripes(image):
                        return [sorted((count,bytes(rgb).hex()) for count,rgb in
                                image.crop((x,0,x+4,6)).getcolors()) for x in range(0,16,4)]
                    row.update(stripes=stripes(last_frame[0]),reference_stripes=stripes(reference))
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
            pair=dict(tag=tag,scene=scene,step=last,archive_sha256=archive_hash,
                transport=tx,capture=ev['capture'],renderer=ev['requested_renderer'],actual_renderer=ev['actual_renderer'],font=os.environ['NEMOTERM_TEST_FONT'],cells=ev['cell_pixels'],
                product_sha256=ev['executable_sha256'],reference_exe_sha256=facts['executable_sha256'],
                frames=comparisons,before_vs_after=mismatches(before,after),
                historical_pixel_failures=historical_failures,capture_failures=capture_failures,reply_failures=reply_failures)
            write_snapshot(capture_dir/'paired.json',pair)
            if write_mode:
                # An all-black/stale GPU capture can agree with a blank reference.
                # Exercise two distinct non-black states after the historical prefix.
                pair['colour_control']=False
                try:
                    for label,left,right in [('rg','red','green'),('gr','green','red')]:
                        rgb={'red':'255;0;0','green':'0;255;0'}
                        wire=(CSI+'?25l'+CSI+'2J'+CSI+'H'+CSI+'48;2;'+rgb[left]+'m '+
                              CSI+'48;2;'+rgb[right]+'m '+CSI+'0m')
                        regions=[dict(x=BORDER+i*6,y=BORDER,width=6,height=13,colour=colour)
                                 for i,colour in enumerate((left,right))]
                        phase('surface-'+label,wire,regions,expected_reply=b'')
                    pair['colour_control']=True
                finally:write_snapshot(capture_dir/'paired.json',pair)
        assert ('--presented-gdi' in sys.argv) != ('--presented-directx' in sys.argv)
        main(exercise,suite_name='regis-window-pair-'+tag, before_exercise=ev.update,prepare_window=resize_grid,
             font=os.environ['NEMOTERM_TEST_FONT'],child_write_mode=write_mode,profile_values=dict(NemoTabs=0,LockSize=2,**({'NemoAllowChecksum':1} if motion else {})))
    # A mismatch must not prevent subsequent frame capture or natural cleanup.
    if historical_failures or capture_failures or reply_failures: sys.exit(f'{tag}: historical pixels {historical_failures}, capture {capture_failures}, replies {reply_failures}')


if __name__=='__main__': run(sys.argv.pop(1))
