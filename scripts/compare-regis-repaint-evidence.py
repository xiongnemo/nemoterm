"""Join saved component RGB and independent XTerm repaint evidence without running a terminal."""
import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile
from PIL import Image, ImageChops


def digest(data):
    return hashlib.sha256(data).hexdigest()


def image(archive, name, crop=False):
    with Image.open(io.BytesIO(archive.read(name))) as source:
        result=source.convert('RGB')
    if crop:
        assert result.width>=162 and result.height>=122
        result=result.crop((2,2,162,122))
    assert result.size==(160,120)
    return result


def difference(a,b):
    r,g,b=ImageChops.difference(a,b).split()
    mask=ImageChops.lighter(ImageChops.lighter(r,g),b)
    return mask.width*mask.height-mask.histogram()[0]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component',type=Path);parser.add_argument('archive_sha256');parser.add_argument('output',type=Path)
    args=parser.parse_args();data=args.component.read_bytes();assert digest(data)==args.archive_sha256
    root=Path(__file__).resolve().parents[1]/'testdata/upstream'
    with ZipFile(root/'regis-reference-evidence.zip') as wrapper:
        first=wrapper.read('44093439244/14331564743.zip')
    second=(root/'regis-repaint-reference.zip').read_bytes()
    assert digest(first)=='f1cb288263b12e35be6ffc29b4edde6f71ee65054adabb1c105198ccdaf25b00'
    assert digest(second)=='ca9165f9d14cb8ef67840a3c46063fde3d4f9dc104ac58086bc9b125c79fac4f'
    output=dict(component_archive_sha256=digest(data),original_archive_sha256=digest(first),repaint_archive_sha256=digest(second),transports={})
    with ZipFile(io.BytesIO(data)) as c, ZipFile(io.BytesIO(first)) as orig, ZipFile(io.BytesIO(second)) as exp:
        baseline,exposed=[json.loads(z.read('observations.json')) for z in (orig,exp)]
        assert all(d['completed'] and not d['control_failures'] and not d['transport_mismatches'] for d in (baseline,exposed))
        for t in ('whole','bytewise'):
            key,=[n for n in c.namelist() if n.endswith('views-'+t+'/observations.json')];prefix=key.rsplit('/',1)[0]
            obs=json.loads(c.read(key));assert obs['completed'] and obs['reference_archive_sha256']==digest(first) and obs['transport']==t
            assert set(obs['cases']) | set(obs['excluded']) == set(baseline['cases'])
            record=dict(fixture_commit=obs['fixture_commit'],executable_sha256=obs['executable_sha256'],excluded=obs['excluded'],frames=0,differences=[])
            for name,case in obs['cases'].items():
                variant=baseline['cases'][name]['whole'];other=exposed['cases'][name][t]
                assert not case['exit_code'] and variant['completed'] and other['completed']
                assert len(case['steps'])==len(variant['steps'])==len(other['steps'])
                for i,(item,old,new) in enumerate(zip(case['steps'],variant['steps'],other['steps'])):
                    assert old['sequence_hex']==new['sequence_hex'] and old['reply_hex']==new['reply_hex']
                    original=image(orig,'observations/'+name+'-whole/'+old['frame']['file'],True)
                    assert digest(original.tobytes())==item['reference_crop_sha256']
                    actual=image(c,f'{prefix}/{name}-{i}-actual.png') if item['pixel_mismatches'] else original
                    assert digest(actual.tobytes())==item['rgb_sha256']
                    assert difference(actual,original)==item['pixel_mismatches']
                    exposed_image=image(exp,'observations/'+name+'-'+t+'/'+new['repaint']['file'],True)
                    mm=0 if actual.tobytes()==exposed_image.tobytes() else difference(actual,exposed_image)
                    if mm or item['pixel_mismatches']:
                        record['differences'].append(dict(scene=name,step=i,historical=item['pixel_mismatches'],exposed=mm,
                            actual_rgb_sha256=item['rgb_sha256'],exposed_rgb_sha256=digest(exposed_image.tobytes())))
                    record['frames']+=1
            output['transports'][t]=record
    args.output.write_text(json.dumps(output,indent=2)+'\n',encoding='utf8')


if __name__=='__main__':main()
