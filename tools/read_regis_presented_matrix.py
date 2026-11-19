"""Summarize downloaded presented-matrix evidence offline; never launch Nemoterm."""
import argparse
import hashlib
import io
import json
from pathlib import PureWindowsPath
from zipfile import ZipFile

from PIL import Image


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inspect(path):
    tracks, result = {}, {}
    with ZipFile(path) as outer:
        source = json.loads(outer.read('source.json'))
        for artifact in source['artifacts']:
            raw = outer.read(artifact['name'] + '.zip')
            assert 'sha256:' + digest(raw) == artifact['digest'] and len(raw) == artifact['size_in_bytes']
            _, _, renderer, mode, _, _ = artifact['name'].split('-')
            key = f'{renderer}/{mode}'
            assert key not in tracks
            phases = tracks[key] = {}
            summary = result[key] = dict(completed=[], acquisition_errors={}, historical={}, geometry_wait_ms=[])
            with ZipFile(io.BytesIO(raw)) as z:
                manifest = json.loads(z.read('build/frame-pair-product/SOURCE-HOST.json'))
                assert manifest['Executable']['SHA256'] == source['product_sha256']
                observations = [n for n in z.namelist() if n.endswith('-observed.json')]
                assert len(observations) == 10
                for n in sorted(observations):
                    o = json.loads(z.read(n))
                    tag = n.split('regis-window-pair-',1)[1].split('-presented-',1)[0]
                    assert o['executable_sha256'] == source['product_sha256']
                    if not o['completed']:
                        summary['acquisition_errors'][tag] = o.get('error', 'incomplete')
                        continue
                    folder = 'research/' + PureWindowsPath(o['folder']).name + '/'
                    pair = json.loads(z.read(folder + 'paired.json'))
                    assert (pair['tag'], pair['renderer'], pair['transport']) == (tag, renderer, mode)
                    assert pair['actual_renderer'] == {'gdi':0,'directx':2}[renderer] and pair['cells'] == [6,13]
                    assert pair['product_sha256'] == source['product_sha256'] and pair['colour_control']
                    assert not o['cleanup']['terminated_remaining'] and not pair['capture_failures']
                    summary['completed'].append(tag)
                    if history := o['presented_capture'].get('initial_geometry'):
                        assert history[-1]['rects'][0] == history[-1]['rects'][1]
                        summary['geometry_wait_ms'].append(history[-1]['ms'])
                    if pair['historical_pixel_failures']:
                        summary['historical'][tag] = {k: pair['frames'][k]['last_difference']['pixels'] for k in pair['historical_pixel_failures']}
                    for check in o['checks']:
                        label = check['name']; phase = f'{tag}/{label}'
                        assert phase not in phases and check['matched'] and check['reply_hex'] == check['expected_reply_hex']
                        wire = bytes.fromhex(check['sequence_hex'] + check['barrier_sequence_hex'])
                        receipt = check['output_write']
                        assert receipt == dict(style=mode, api='WriteFile(console stdout)', calls=len(wire) if mode=='bytewise' else 1,
                                               bytes=len(wire), max_chunk=1 if mode=='bytewise' else len(wire), sha256=digest(wire))
                        bmp = z.read(folder + check['bmp']); assert digest(bmp) == check['bmp_sha256']
                        image = Image.open(io.BytesIO(bmp)).convert('RGB'); assert image.size == (242,158)
                        pixels = digest(image.crop((1,1,161,121)).tobytes())
                        if label in pair['frames']: assert pixels == pair['frames'][label]['last_sha256']
                        phases[phase] = (pixels, receipt['sha256'], check['reply_hex'])
    baseline = tracks['gdi/whole']
    for key, track in tracks.items():
        result[key]['phases'] = len(track)
        result[key]['unpaired_phases'] = sorted(set(baseline) ^ set(track))
        result[key]['different_from_gdi_whole'] = sorted(k for k in baseline.keys() & track.keys() if baseline[k] != track[k])
    return dict(run=source['run'], sha256=source['product_sha256'], results=result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive')
    print(json.dumps(inspect(parser.parse_args().archive), indent=2))
