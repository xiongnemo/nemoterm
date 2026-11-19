"""Review two downloaded Actions selection artifacts without launching either EXE."""
import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image


# Targets are the screen displayed after the mode request. Only replacement or
# erasure of the visible grid should invalidate the selected glyphs.
CASES = {
    'main-released': ('?47l', False, False, True),
    'main-pressed': ('?1049l', True, False, True),
    'alternate-released': ('?1047h', False, True, True),
    'alternate-pressed': ('?47h', True, True, True),
    'enter-alternate': ('?47h', True, True, False),
    'leave-alternate': ('?1047l', False, False, False),
    'erase-alternate': ('?1049h', True, True, False),
}
ACK = b'\x1b[0n'


def read(path):
    result = {}
    with ZipFile(path) as archive:
        def read_json(name):
            return json.loads(archive.read(name).decode('utf-8-sig'))
        stage = read_json('interaction/identity.json')
        source = read_json('interaction-product/SOURCE-HOST.json')
        rows = read_json('interaction/results.json')
        product = source['Executable']['SHA256']
        assert not stage['fixture_dirty'] and product == stage['executable_sha256']
        for renderer, backend in [('gdi', 1), ('directx', 3)]:
            case, = (r for r in rows if r['id'] == 'selection-'+renderer)
            def evidence(name):
                key = 'research/'+name
                data = archive.read('interaction/'+case['directory']+'/'+key)
                assert sha256(data).hexdigest() == case['evidence'][key], key
                return data
            obs = json.loads(evidence('tabs-selection-observed.json'))
            assert obs['executable_sha256'] == product and obs['active_renderer'] == backend
            assert obs['requested_font'] == 'SarasaTermSC Nerd Light' and obs['tab_host']
            assert not case['cleanup']['terminated_remaining'] and not case['cleanup']['remaining_processes']
            cw, ch = obs['cell_pixels']
            results = {}
            physical = obs['split_system_input']
            assert physical['focus']['completed']
            expected_events = []
            expected_motion = []
            for r in obs['screen_selection']:
                name = r['case']
                command, held, target, survives = CASES[name]
                assert r['command'] == command and r['held'] is held and r['survives'] is survives
                assert name not in results, name
                releases = [[16,False],['left',False]] if held else [['left',False],[16,False]]
                expected_events.extend([[16,True],['left',True]] + releases + [['right',True],['right',False]])
                expected_motion.extend([[1+x*cw+cw//2, 1+6*ch+ch//2] for x in (2,4)])
                image = Image.open(BytesIO(evidence('screen-'+name+'.png'))).convert('RGB')
                def cell(x, y):
                    left, top = 1+x*cw, 1+y*ch
                    return image.crop((left,top,left+cw,top+ch)).tobytes()
                # The reference row must contain actual glyphs, not two equally
                # blank rows that happen to agree after a clear.
                for x in range(1,6):
                    data = cell(x,8)
                    assert len({data[i:i+3] for i in range(0,len(data),3)}) > 1, (name,x)
                changed = [x for x in range(7) if cell(x,6)!=cell(x,8)]
                assert changed == r['highlight'], (name,changed,r['highlight'])
                reply = (b'\x1b[?47;' + (b'1' if target else b'2') +
                         b'$y\x1b[?1002;1$y\x1b[?1006;1$y'+ACK)
                right = b'' if survives else b'\x1b[<2;5;7M\x1b[<2;5;7m'
                checks = dict(mode=r['mode_wire']==reply.hex(), gesture=r['gesture_wire']==(ACK*2).hex(),
                              highlight=changed==([2,3,4] if survives else []),
                              right=r['right_wire']==(ACK+right+ACK).hex(), copy=r['copied']==('BCD' if survives else None))
                assert all(checks.values()) == r['passed'], (name, checks, r['passed'])
                results[name] = {'passed':r['passed'], 'failed_checks':[k for k,v in checks.items() if not v]}
            assert list(results) == list(CASES), list(results)
            assert physical['events'][-len(expected_events):] == expected_events
            assert [m['client'] for m in physical['motion'][-len(expected_motion):]] == expected_motion
            result[renderer] = {'stage_status':case['status'], 'cases':results}
    return dict(commit=source['SourceCommit'], executable_sha256=product, fixture_commit=stage['fixture_commit'],
                renderers=result), stage['snapshot_hashes']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path); parser.add_argument('after', type=Path)
    args = parser.parse_args()
    old, a = read(args.before); new, b = read(args.after)
    assert {k for k in a.keys()|b.keys() if a.get(k)!=b.get(k)} == {'dist/nemoterm.exe'}
    assert old['executable_sha256'] != new['executable_sha256']
    print(json.dumps({'before':old,'after':new}, indent=2))


if __name__ == '__main__':
    main()
