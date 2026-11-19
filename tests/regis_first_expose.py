"""Compare fresh, unexposed XTerm input prefixes to the immutable first-display record."""
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile
from PIL import Image


# One fresh process per endpoint, even when two endpoints share the same prefix.
def targets():
    points = {'scroll-up': (2,), 'scroll-down': (1, 2), 'newline-scroll': (2,),
              'regis-palette-False': (1,), 'erase-line': (1, 2),
              'control-text': (1,), 'control-line-erase': (1, 2)}
    return {f'{scene}-end-{n}': (scene, n) for scene, ends in points.items() for n in ends}


def verify_prefixes(result, base):
    old_digest = 'f1cb288263b12e35be6ffc29b4edde6f71ee65054adabb1c105198ccdaf25b00'
    with ZipFile(Path(__file__).resolve().parents[1]/'testdata/upstream/regis-reference-evidence.zip') as outer:
        data = outer.read('44093439244/14331564743.zip')
    assert hashlib.sha256(data).hexdigest() == old_digest
    result.update(original_archive_sha256=old_digest,
                  prefix_verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    failures = []
    with ZipFile(io.BytesIO(data)) as archive:
        old = json.loads(archive.read('observations.json'))
        assert old['completed'] and not old['control_failures'] and not old['transport_mismatches']
        for tag, (scene, last) in targets().items():
            for tx in ('whole', 'bytewise'):
                row = result['cases'][tag][tx]
                original = old['cases'][scene][tx]
                if not row['completed'] or len(row['steps']) != last+1:
                    failures.append([tag, tx, 'incomplete capture']); continue
                if row['cell_pixels'] != original['cell_pixels'] or row['initial_frame']['rgb_sha256'] != original['initial_frame']['rgb_sha256']:
                    failures.append([tag, tx, 'initial frame/geometry'])
                for i, step in enumerate(row['steps']):
                    ref = original['steps'][i]
                    for field in ('sequence_hex', 'wire_with_barrier_hex', 'reply_with_barrier_hex', 'reply_hex'):
                        if step[field] != ref[field]: failures.append([tag, tx, i, field])
                    if step['frame']['rgb_sha256'] != ref['frame']['rgb_sha256']:
                        failures.append([tag, tx, i, 'historical first presentation'])
                    if ('repaint' in step) != (i == last): failures.append([tag, tx, i, 'expose position'])
                final = row['steps'][-1]
                if final.get('repaint_barrier_hex') != '1b5b306e':
                    failures.append([tag, tx, 'exposure not acknowledged']); continue
                for key in ('frame', 'repaint'):
                    record = final[key]
                    file = base/(tag+'-'+tx)/record['file']
                    with Image.open(file) as im:
                        rgb = im.convert('RGB')
                        if hashlib.sha256(rgb.tobytes()).hexdigest() != record['rgb_sha256']:
                            failures.append([tag, tx, key, 'full frame digest'])
                        record['graphic_crop_rgb_sha256'] = hashlib.sha256(rgb.crop((2,2,162,122)).tobytes()).hexdigest()
                if scene.startswith('control-') and final['frame']['rgb_sha256'] != final['repaint']['rgb_sha256']:
                    failures.append([tag, tx, 'control not restored by expose'])
    return failures
