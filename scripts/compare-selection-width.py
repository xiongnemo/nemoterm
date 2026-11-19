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


def reflow_cases(evidence, obs):
    """Read glyph locations and highlight from original frames, not the fixture verdict."""
    cw, ch = obs['cell_pixels']
    word = '|ABCDEFGH|'
    cases = {'stream': (3, 8, True), 'reverse-press': (3, 8, True),
             'rectangle': (5, 8, True), 'split-rectangle': (3, 8, False)}
    records = {}
    for row in obs['reflow_selection']:
        name = row['case']; first, end, survives = cases[name]
        assert name not in records
        report = records[name] = {'frames': {}}
        checks = {}
        for f in row['frames']:
            stage = f['stage']; cols = 74 if stage == 'narrow' else 80
            im = Image.open(BytesIO(evidence(f'reflow-{name}-{stage}.png'))).convert('L')
            assert cols == f['cols'] and im.size == (2 + cols*cw, 2 + 24*ch)
            def glyph(x, y):
                t = im.crop((1+x*cw, 1+y*ch, 1+(x+1)*cw, 1+(y+1)*ch))
                lo, hi = t.getextrema(); assert lo != hi
                bg = max(t.getcolors(), key=lambda item: item[0])[1]
                # Use foreground contrast relative to this tile's own background
                # so reversing a selected glyph's colours doesn't change its label.
                return bg, tuple(abs(px-bg) > (hi-lo)*.22 for px in t.tobytes())
            reference = [glyph(x, 2) for x in range(len(word))]
            highlights = []
            for i, letter in enumerate(word):
                bg, mask = glyph((69+i)%cols, 6+(69+i)//cols)
                distances = [sum(a!=b for a,b in zip(mask,ref)) for _,ref in reference]
                closest = {c for c,n in zip(word,distances) if n==min(distances)}
                assert closest == {letter}, (name,stage,i,closest)
                if bg != reference[i][0]: highlights.append(i)
            want = list(range(first,end)) if stage=='selected' or (stage!='initial' and survives) else []
            assert want == f['expected'] and highlights == f['highlight']
            checks[stage] = highlights == want
            report['frames'][stage] = highlights
        stages = ['initial'] + ([] if name=='reverse-press' else ['selected']) + ['narrow','wide']
        assert list(report['frames']) == stages
        text = word[first:end] if survives else None
        wire = b'' if survives else b'\x1b[<2;77;7M\x1b[<2;77;7m'
        checks['gesture'] = row['gesture_wire']==(b'\x1b[?47;2$y\x1b[?1002;1$y\x1b[?1006;1$y'+ACK*2).hex()
        checks['copy'] = row.get('copied')==text and (not survives or row['copy_wire']==(ACK*2).hex())
        checks['right'] = row['right_copy']==text and row['right_wire']==(ACK+wire+ACK).hex()
        if 'narrow_copy' in row: checks['copy_while_wrapped'] = row['narrow_copy']==dict(text=text,wire=(ACK*2).hex())
        report.update(copied=row.get('copied'), narrow_copy=row.get('narrow_copy'), checks=checks, passed=all(checks.values()))
        assert report['passed'] == row['passed']
    assert records.keys()==cases.keys()
    return records


def unicode_cases(evidence, obs):
    # One reference tile for each half of 中; the plain e following the
    # reference is a negative control for dropping the combining accent.
    cw, ch = obs['cell_pixels']; labels = ('|','A','B','Q','中L','中R','é','V','|','e')
    records = {}
    for r in obs['reflow_unicode']:
        name = r['case']; held = name=='unicode-trailing-press'; text = ('中' if held else 'Q中')+'e\u0301'
        checks = {}; highlights = {}; masks = {}
        for f in r['frames']:
            stage = f['stage']; narrow = stage=='narrow'; w = 74 if narrow else 80
            im = Image.open(BytesIO(evidence(name+'-'+stage+'.png'))).convert('L')
            assert im.size == (2+w*cw,2+24*ch)
            def shape(x,y):
                tile = im.crop((1+x*cw,1+y*ch,1+(x+1)*cw,1+(y+1)*ch)); lo,hi=tile.getextrema()
                bg = max(tile.getcolors(), key=lambda it:it[0])[1]
                return bg, bytes(abs(v-bg)>(hi-lo)*.28 for v in tile.tobytes())
            types = [shape(i,2) for i in (*range(9),10)]; marks=[]; chars=[]
            for i in range(9):
                bg,cell = shape(i-4,7) if narrow and i>=4 else shape(69+i,6)
                delta = [sum(a!=b for a,b in zip(cell,ref)) for _,ref in types]
                # A selected tile uses the opposite text/background colours.
                # Whole-tile distance against unaccented e is unstable with
                # subpixel AA. Inspect the accent above the actual base glyph.
                nearest = min(delta[:9]); chars.append(sorted({k for k,d in zip(labels[:9],delta[:9]) if d==nearest}))
                if i==6:
                    accent_rows = [y for y in range(ch) if not any(types[9][1][y*cw:(y+1)*cw])
                                   and any(types[6][1][y*cw:(y+1)*cw])]
                    accent_ink = bool(accent_rows) and any(cell[y*cw+x] and types[6][1][y*cw+x]
                                                          for y in accent_rows for x in range(cw))
                if bg!=types[i][0]: marks.append(i)
            pad_empty = not any(shape(73,6)[1]) if narrow else None
            assert marks==f['highlight'] and pad_empty==f['pad_blank']
            checks[stage+'_accent'] = accent_ink
            checks[stage] = chars==[[k] for k in labels[:9]] and pad_empty is not False and marks==([] if stage=='initial' else list(range(4 if held else 3,7)))
            highlights[stage] = marks; masks[stage] = chars
        assert list(highlights)==(['initial','narrow','wide'] if held else ['initial','selected','narrow','wide'])
        checks['gesture'] = r['gesture_wire']==(b'\x1b[?47;2$y\x1b[?1002;1$y\x1b[?1006;1$y'+ACK*2).hex()
        for key in ('narrow','wide','right'): checks['copy_'+key]=r[key]=={'text':text,'wire':(ACK*2).hex()}
        ok=all(checks.values());assert ok==r['passed'], (name,checks,masks);assert name not in records
        records[name]=dict(passed=ok,checks=checks,highlight=highlights,glyphs=masks,clipboard={k:r[k] for k in ('narrow','wide','right')})
    assert set(records)=={'unicode-span','unicode-trailing-press'}
    return records


def inspect(path, reflow=False, unicode=False):
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
            if unicode:
                result['renderers'][renderer] = unicode_cases(evidence, obs)
                continue
            if reflow:
                result['renderers'][renderer] = reflow_cases(evidence, obs)
                continue
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
    group=p.add_mutually_exclusive_group()
    group.add_argument('--unicode', action='store_true', help='Inspect wide glyphs and combining marks across a wrap')
    group.add_argument('--reflow', action='store_true', help='Inspect main-screen split/merge frames')
    args=p.parse_args();before, old=inspect(args.before,args.reflow,args.unicode);result={'before':before}
    if args.after:
        after, new=inspect(args.after,args.reflow,args.unicode)
        assert old.keys()==new.keys() and {k for k in old if old[k]!=new[k]}=={'dist/nemoterm.exe'}
        assert before['sha256']!=after['sha256'];result['after']=after
    print(json.dumps(result, indent=2))
