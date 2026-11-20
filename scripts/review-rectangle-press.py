"""Review rectangular redraws from an unmodified hosted interaction-selection ZIP."""
import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image


# Columns include both endpoints and are independent of the recorded check result.
EXPECTED = {
    'fill-replaced': None, 'fill-identical': (10, 12, 'KLM'),
    'fill-neighbour': (10, 12, 'KZM'), 'fill-wide-tail': None,
    'fill-strips-accent': None, 'fill-bidi-neighbour': (9, 10, 'אX'),
    'copy-replaced': None, 'copy-from-press': (10, 12, 'KLM'),
    'copy-overlap': None, 'copy-wide-tail': None,
    'copy-same-accent': (10, 12, 'K\u0301LM'), 'copy-new-accent': None,
}
PHYSICAL = {'fill-replaced', 'fill-identical', 'copy-overlap', 'copy-same-accent'}
WINDOWS = {'selection-gdi': 1, 'selection-profile-font-gdi': 1,
           'selection-directx': 3, 'selection-profile-font-directx': 3}
ACK = b'\x1b[0n'


def review(archive):
    def read(path):
        return json.loads(archive.read(path).decode('utf-8-sig'))

    source = read('interaction-product/SOURCE-HOST.json')
    identity = read('interaction/identity.json')
    sha = source['Executable']['SHA256'].lower()
    assert identity['executable_sha256'] == sha
    windows = set()
    results = []
    for row in read('interaction/results.json'):
        window = row['id']
        if window not in WINDOWS:
            continue
        assert window not in windows
        windows.add(window)
        tab = '-profile-font-' not in window
        attempt = row['directory'].replace('\\', '/').rsplit('/', 1)[-1]
        assert attempt.startswith(window+'-') and attempt[len(window)+1:].isdigit()

        def owned(name):
            member = 'research/'+name
            raw = archive.read('interaction/attempts/'+attempt+'/'+member)
            assert hashlib.sha256(raw).hexdigest() == row['evidence'][member], member
            return raw

        obs = json.loads(owned(('tabs-' if tab else '')+'selection-observed.json'))
        assert obs['executable_sha256'] == sha and obs['active_renderer'] == WINDOWS[window]
        assert obs['tab_host'] == tab and obs['requested_font'] == ('SarasaTermSC Nerd Light' if tab else None)
        cw, ch = obs['cell_pixels']
        for channel, key in [('message', 'horizontal_press'), ('physical', 'horizontal_press_system')]:
            selected = [v for v in obs.get(key, []) if v['case'] in EXPECTED]
            names = set(EXPECTED) if channel == 'message' else PHYSICAL if tab else set()
            assert {v['case'] for v in selected} == names and len(selected) == len(names)
            for v in selected:
                case = v['case']
                want = EXPECTED[case]
                x, y = v['released']
                image = Image.open(io.BytesIO(owned(f'{channel}-column-{case}.png'))).convert('RGB')
                assert image.size == (80*cw+2, 24*ch+2)
                # The lower scanline gives the background independently of the glyph ink.
                # Limit this oracle to the captured default colours and these two fonts.
                columns = []
                for i in range(80):
                    line = image.crop((1+i*cw, (y+1)*ch, 1+(i+1)*cw, (y+1)*ch+1))
                    count, colour = max(line.getcolors(cw))
                    assert colour in ((0, 0, 0), (187, 187, 187)) and count*2 > cw, (case, i, colour, count)
                    if colour == (187, 187, 187):
                        columns.append(i)
                text = want[2] if want else None
                marks = list(range(want[0], want[1]+1)) if want else []
                right = b'' if want else f'\x1b[<2;{x+1};{y+1}M\x1b[<2;{x+1};{y+1}m'.encode()
                checks = dict(pixels=columns == marks, observed_highlight=columns == v['highlight'],
                              clipboard=v['clipboard_changed'] == bool(want) and v['right_copy'] == v['shortcut_copy'] == text,
                              no_gesture_leak=bytes.fromhex(v['gesture_wire']) == ACK*2,
                              right_owner=bytes.fromhex(v['right_wire']) == ACK+right+ACK,
                              held_glyph=not want or v['same_glyph_pixels'])
                results.append(dict(window=window, channel=channel, case=case, right_copy=v['right_copy'],
                                    columns=columns, checks=checks, passed=all(checks.values())))
    assert windows == set(WINDOWS) and len(results) == 56
    return dict(source=source['SourceCommit'], sha256=sha, fixture=identity['fixture_commit'],
                passed=sum(x['passed'] for x in results), total=len(results), cases=results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact', type=Path)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    with ZipFile(args.artifact) as archive:
        result = review(archive)
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"{result['source']} {result['passed']}/{result['total']}")
    raise SystemExit(result['passed'] != result['total'])
