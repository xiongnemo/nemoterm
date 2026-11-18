"""Compare OSC replies and the actual Windows cursor with a retained XTerm run."""
from collections import Counter
import hashlib
import json
import os
import time
import zipfile

from native_test_utils import read_snapshot, wait_for, write_snapshot


REFERENCE = '9d53c96d09b1e313c853f9767e246c403d1f86a681437e79e15b1e3a055bb346'
DSR = b'\x1b[5n'
OK = b'\x1b[0n'


def compare_cursor_colours(reference, child, seat, out, evidence, native_cursor,
                           pointer_png, point_in, emit, publish):
    assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
    assert hashlib.sha256(reference.read_bytes()).hexdigest() == REFERENCE
    with zipfile.ZipFile(reference) as z:
        profile = json.loads(z.read('pointer-colour/default/observed.json'))
        assert profile['completed'] and profile['exit_code'] == 0 and len(profile['steps']) == 19
        evidence['reference'] = dict(archive_sha256=REFERENCE, profile='default',
                                     identity=json.loads(z.read('pointer-colour/identity.json')))
    checks = evidence['colour_checks'] = []
    failures = evidence['colour_failures'] = []
    # A native monochrome cell glyph gives both inks a defined shape. OSC 22 is
    # separate from the colour commands collected in the XTerm reference.
    emit(child, '\x1b]22;cell\x1b\\', 'cell')
    point_in(seat)
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
        while True:
            rec, image, counts = sample()
            if expected.issubset(counts) and reverse_matches(image): break
            if time.monotonic() >= until: break
            time.sleep(.04)
        rec, image, counts = sample(str(out / (phase+'.png')))
        result = dict(stage=stage, input_hex=wire.hex(), expected_reply_hex=row['reply_hex'],
                      reply_hex=reply.hex(), reply_matches=reply.hex()==row['reply_hex'],
                      expected_inks=sorted(expected), observed_rgb_counts=counts, os_cursor=rec,
                      inks_present=expected.issubset(counts), reverse_matches=reverse_matches(image))
        checks.append(result)
        if not (result['reply_matches'] and result['inks_present'] and result['reverse_matches']):
            failures.append(stage)
        previous_image = image
        publish()
