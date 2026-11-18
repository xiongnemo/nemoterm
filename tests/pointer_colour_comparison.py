"""Compare OSC replies and the actual Windows cursor with a retained XTerm run."""
from collections import Counter
import hashlib
import json
import os
import struct
import time
import zipfile

from native_test_utils import read_snapshot, wait_for, write_snapshot


REFERENCE = '45d1b8c67962304696bf583e035c051bfbf257d362ec1ffadd1a799d80974770'
DSR = b'\x1b[5n'
OK = b'\x1b[0n'


def compare_cursor_colours(reference, child, seat, out, evidence, native_cursor,
                           pointer_png, point_in, emit, publish):
    assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
    assert hashlib.sha256(reference.read_bytes()).hexdigest() == REFERENCE
    with zipfile.ZipFile(reference) as z:
        profile = json.loads(z.read('pointer-colour/default/observed.json'))
        assert profile['completed'] and profile['exit_code'] == 0 and len(profile['steps']) == 31
        evidence['reference'] = dict(archive_sha256=REFERENCE, profile='default',
                                     identity=json.loads(z.read('pointer-colour/identity.json')))
    checks = evidence['colour_checks'] = []
    failures = evidence['colour_failures'] = []
    # A native monochrome cell glyph gives both inks a defined shape. OSC 22 is
    # separate from the colour commands collected in the XTerm reference.
    emit(child, '\x1b]22;cell\x1b\\', 'cell')
    point_in(seat)
    stock_handle = evidence['checks'][0]['handle']  # verified against IDC_IBEAM
    previous_image = None
    for row in profile['steps']:
        stage = row['stage']
        phase = 'colour-' + stage
        wire = bytes.fromhex(row['sequence_hex']) + DSR
        write_snapshot(child['control'], dict(phase=phase, sequence=wire.decode('ascii'), preserve_mouse=True))
        def delivered():
            value = read_snapshot(child['report']) or {}
            return value if value.get('phase') == phase and bytes.fromhex(value['hex']).endswith(OK) else None
        reply = bytes.fromhex(wait_for(delivered)['hex'])[:-len(OK)]
        expected = {k[2:] for k in row['cursor']['counts'] if k.startswith('ff')}
        # A status report fences terminal parsing, not the repaint timer.
        # Sample the real selected OS handle until both requested inks appear;
        # retain an image and report even when the unchanged product ignores OSC.
        until = time.monotonic() + 1.5
        def sample(path=None):
            rec, _ = native_cursor()
            if not rec.get('handle') or not (rec['flags'] & 1):
                return rec, b'', {}
            image = pointer_png(rec, path)
            counts = Counter(image[i:i+3].hex() for i in range(0, len(image), 3))
            return rec, image, dict(counts)
        def reverse_matches(image):
            if stage != 'reverse': return True
            if not previous_image or not image: return False
            colours = [bytes.fromhex(v) for v in sorted(expected)]
            swap = {colours[0]:colours[1], colours[1]:colours[0]}
            return (all(image[i:i+3] == swap.get(previous_image[i:i+3], previous_image[i:i+3])
                        for i in range(0, len(previous_image), 3)) and previous_image != image)
        stock_expected = stage in ('plain-reset-both', 'soft-plain-resets', 'ris-plain-resets', 'unchanged-pop-resets')
        def presentation(rec, counts):
            # Both resets restore the unmodified system cursor; its themed ink
            # on this runner need not be the literal default black and white.
            if stock_expected: return rec.get('handle') == stock_handle
            return expected.issubset(counts)
        while True:
            rec, image, counts = sample()
            if presentation(rec, counts) and reverse_matches(image): break
            if time.monotonic() >= until: break
            time.sleep(.04)
        rec, image, counts = sample(str(out / (phase+'.png')))
        result = dict(stage=stage, input_hex=wire.hex(), expected_reply_hex=row['reply_hex'],
                      reply_hex=reply.hex(), reply_matches=reply.hex()==row['reply_hex'],
                      expected_inks=sorted(expected), observed_rgb_counts=counts, os_cursor=rec,
                      inks_present=expected.issubset(counts), stock_expected=stock_expected,
                      presentation_matches=presentation(rec,counts), reverse_matches=reverse_matches(image))
        checks.append(result)
        if not (result['reply_matches'] and result['presentation_matches'] and result['reverse_matches']):
            failures.append(stage)
        previous_image = image
        publish()


def check_colour_tabs(api, endpoint, host, first, first_child, child_for, out, evidence,
                      native_cursor, pointer_png, point_in, emit, publish):
    """New tab starts with its theme; updates from a hidden tab stay local."""
    st='\x1b\\'
    def sequence(fg,bg): return '\x1b]13;#'+fg+';#'+bg+st+'\x1b]22;cell'+st
    def check_pixels(label, seat, inks):
        point_in(seat)
        result=dict(label=label, session=seat['id'], inks=inks)
        evidence.setdefault('tab_colours',[]).append(result)
        def capture():
            rec,_=native_cursor()
            result['cursor']=rec
            if not rec.get('handle') or not rec['flags']&1: return False
            image=pointer_png(rec,None)
            counts=Counter(image[i:i+3].hex() for i in range(0,len(image),3))
            result['counts']=dict(counts)
            return all(counts[ink] for ink in inks)
        try:
            wait_for(capture)
            pointer_png(result['cursor'],str(out/(label+'.png')))
        finally:publish()
    emit(first_child,sequence('10b849','bf2497'),'cell')
    check_pixels('first-tab-inks',first,['10b849','bf2497'])
    api.request(endpoint,'key',first['id'],struct.pack('<II',ord('T'),3))
    sessions=wait_for(lambda:(s if len(s:=api.request(endpoint)['sessions'])==2 else None))
    second=next(s for s in sessions if s['id']!=first['id']);second_child=child_for(second)
    assert second['active'] and second['window']==host
    point_in(second)
    stock=evidence['checks'][0]['handle']
    wait_for(lambda:native_cursor()[0].get('handle')==stock)
    emit(second_child,sequence('276ede','e1ac19'),'cell')
    check_pixels('second-tab-inks',second,['276ede','e1ac19'])
    before=native_cursor()[0]['handle']
    emit(first_child,sequence('e93057','2bd6ce'),'cell')
    samples=evidence['hidden_colour_updates']=[]
    for _ in range(25):
        cur,_=native_cursor();samples.append(cur['handle']);assert cur['handle']==before,cur
        time.sleep(.01)
    api.request(endpoint,'key',second['id'],struct.pack('<II',9,2))
    wait_for(lambda:next(s for s in api.request(endpoint)['sessions'] if s['id']==first['id'])['active'])
    check_pixels('first-tab-updated-inks',first,['e93057','2bd6ce'])
    emit(first_child,'\x1b]113'+st+'\x1b]114'+st+'\x1b]22;text'+st,'text')
    wait_for(lambda:native_cursor()[0].get('handle')==stock)
    evidence['tab_colour_stock_restored']=True
    publish()
