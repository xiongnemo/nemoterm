"""Compare downloaded window-width selection records and PNGs without launching a product."""
import argparse
import hashlib
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image


ACK = b'\x1b[0n'
CASES = {'alternate-wider': (4, 'BCD'), 'alternate-narrower-block': (-6, 'BCD\r\nbcd'),
         'alternate-lost-column': (-6, None)}


def inspect(path):
    with ZipFile(path) as z:
        def read(name):
            return json.loads(z.read(name).decode('utf-8-sig'))
        identity = read('interaction/identity.json')
        source = read('interaction-product/SOURCE-HOST.json')
        rows = read('interaction/results.json')
        sha = source['Executable']['SHA256']
        assert identity['executable_sha256'] == sha and not identity['fixture_dirty']
        result = dict(commit=source['SourceCommit'], sha256=sha, fixture=identity['fixture_commit'], renderers={})
        for renderer, number in [('gdi', 1), ('directx', 3)]:
            case, = (v for v in rows if v['id'] == 'selection-'+renderer)
            def evidence(name):
                key = 'research/'+name
                data = z.read('interaction/'+case['directory']+'/'+key)
                assert hashlib.sha256(data).hexdigest() == case['evidence'][key]
                return data
            obs = json.loads(evidence('tabs-selection-observed.json'))
            assert obs['executable_sha256'] == sha and obs['active_renderer'] == number and obs['tab_host']
            assert obs['requested_font'] == 'SarasaTermSC Nerd Light' and obs['split_system_input']['focus']['completed']
            assert not case['cleanup']['terminated_remaining'] and not case['cleanup']['remaining_processes']
            cw, ch = obs['cell_pixels']
            records = result['renderers'][renderer] = {}
            for r in obs['width_selection']:
                name = r['case']; delta, text = CASES[name]; assert name not in records
                im = Image.open(BytesIO(evidence('height-'+name+'.png'))).convert('RGB')
                assert tuple(r['resized']) == im.size == (r['before'][0]+delta*cw, r['before'][1])
                def colours(x, y):
                    return sorted(im.crop((1+x*cw, 1+y*ch, 1+(x+1)*cw, 1+(y+1)*ch)).getcolors(cw*ch), reverse=True)
                block = name == 'alternate-narrower-block'
                highlight = []
                for y in range(1+int(block)):
                    background = colours(0,6+y)[0][1]
                    for x in range(7):
                        tile = colours(x,6+y)
                        assert len(tile)>1, (name, x, y, 'missing glyph')
                        if tile[0][1] != background: highlight.append([x,y])
                assert highlight == r['highlight'], (name, highlight, r['highlight'])
                expected = [[x,y] for y in range(1+int(block)) for x in (2,3,4)] if text else []
                right = b'' if text else b'\x1b[<2;5;7M\x1b[<2;5;7m'
                checks = dict(highlight=highlight==expected, gesture=r['gesture_wire']==(ACK*2).hex(),
                              copy=r.get('copied')==text and (not text or r['copy_wire']==(ACK*2).hex()),
                              right=r['right_copy']==text and r['right_wire']==(ACK+right+ACK).hex())
                assert all(checks.values()) == r['passed']
                records[name] = dict(passed=r['passed'], highlight=highlight, copied=r.get('copied'),
                                     right_copy=r['right_copy'], right_wire=r['right_wire'], checks=checks)
            assert records.keys()==CASES.keys()
        return result, identity['snapshot_hashes']


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('before', type=Path);p.add_argument('after', type=Path, nargs='?')
    args=p.parse_args();before, old=inspect(args.before);result={'before':before}
    if args.after:
        after, new=inspect(args.after)
        assert old.keys()==new.keys() and {k for k in old if old[k]!=new[k]}=={'dist/nemoterm.exe'}
        assert before['sha256']!=after['sha256'];result['after']=after
    print(json.dumps(result, indent=2))
