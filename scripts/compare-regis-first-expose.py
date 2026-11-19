"""Join saved XTerm first-expose pixels and retained MSVC images; no terminal is run."""
import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile
from PIL import Image, ImageChops


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_rgb(archive, path, expected, crop=False):
    with Image.open(io.BytesIO(archive.read(path))) as src:
        im = src.convert('RGB')
    if digest(im.tobytes()) != expected:
        raise ValueError(f'{path}: RGB digest mismatch')
    if crop:
        if im.width < 162 or im.height < 122:
            raise ValueError(f'{path}: window smaller than graphics area')
        im = im.crop((2, 2, 162, 122))
    if im.size != (160, 120): raise ValueError(f'{path}: unexpected dimensions {im.size}')
    return im


def difference(a, b):
    r, g, blue = ImageChops.difference(a, b).split()
    mask = ImageChops.lighter(ImageChops.lighter(r,g),blue)
    return dict(pixels=160*120-mask.histogram()[0],bounds=mask.getbbox())


def verified_archive(path, expected):
    data = path.read_bytes()
    if digest(data) != expected: raise ValueError(f'{path}: archive digest mismatch')
    return ZipFile(io.BytesIO(data))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','component'):
        p.add_argument(name,type=Path);p.add_argument(name+'_sha256')
    p.add_argument('output',type=Path);a=p.parse_args()
    with verified_archive(a.reference,a.reference_sha256) as ref, verified_archive(a.component,a.component_sha256) as comp:
        summary=json.loads(ref.read('observations.json'))
        assert summary['completed'] and summary['first_expose'] and not summary['repaint']
        assert not summary['control_failures'] and not summary['transport_mismatches']
        report=dict(first_expose_archive_sha256=a.reference_sha256,component_archive_sha256=a.component_sha256,
                    original_archive_sha256=summary['original_archive_sha256'],fixture=summary['fixture_commit'],
                    reference_xterm=summary['executable_sha256'],transports={})
        for tx in ('whole','bytewise'):
            key,=[k for k in comp.namelist() if k.endswith('views-'+tx+'/observations.json')];prefix=key.rsplit('/',1)[0]
            core=json.loads(comp.read(key));assert core['completed'] and core['transport']==tx and core['reference_archive_sha256']==report['original_archive_sha256']
            rows={}; report['transports'][tx]=dict(component_executable=core['executable_sha256'],component_fixture=core['fixture_commit'],cases=rows)
            for tag,(scene,last) in summary['targets'].items():
                if scene.startswith('control-'):continue  # independently checked in the upstream capture
                record=summary['cases'][tag][tx];assert record['completed'] and len(record['steps'])==last+1
                assert all('repaint' not in row for row in record['steps'][:-1]);end=record['steps'][-1]
                assert end['repaint_barrier_hex']=='1b5b306e'
                obs=core['cases'][scene];assert not obs['exit_code'];part=obs['steps'][last];assert part['reply_matches'] and end['reply_hex']==part['reply_hex']
                def from_ref(key):
                    frame=end[key]; im=load_rgb(ref,'observations/'+tag+'-'+tx+'/'+frame['file'],frame['rgb_sha256'],True)
                    assert digest(im.tobytes())==frame['graphic_crop_rgb_sha256'];return im
                first,exposed=from_ref('frame'),from_ref('repaint');assert digest(first.tobytes())==part['reference_crop_sha256']
                actual=(load_rgb(comp,f'{prefix}/{scene}-{last}-actual.png',part['rgb_sha256']) if part['pixel_mismatches'] else first)
                assert digest(actual.tobytes())==part['rgb_sha256']
                compared=difference(actual,first);assert compared['pixels']==part['pixel_mismatches']
                rows[tag]=dict(scene=scene,step=last,component_rgb=part['rgb_sha256'],presented_rgb=digest(first.tobytes()),exposed_rgb=digest(exposed.tobytes()),
                               product_vs_presented=compared,product_vs_first_expose=difference(actual,exposed),effect_of_expose=difference(first,exposed))
    a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')


if __name__=='__main__': main()
