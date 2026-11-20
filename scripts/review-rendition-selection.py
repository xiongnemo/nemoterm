"""Read hosted selection screenshots and clipboard/input receipts; no terminal is needed."""
import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageChops


# Authored row and physical highlighted columns after the application's change.
# An off-screen anchor cancels selection, and its next independent right click
# (column 14, row 6 in one-based SGR coordinates) belongs to the application.
CASES = {'widen-block': (5, range(8, 14)), 'narrow-block': (11, range(4, 7)),
         'hidden-stream': (5, ()), 'widen-stream': (11, range(8, 14)),
         'same-scale': (5, range(8, 14)), 'enable-margins': (11, range(4, 7)),
         'other-row': (5, range(4, 7))}
SYSTEM = {'widen-block', 'hidden-stream', 'enable-margins'}
WINDOWS = {'selection-gdi': 1, 'selection-directx': 3,
           'selection-profile-font-gdi': 1, 'selection-profile-font-directx': 3}
ACK = b'\x1b[0n'


def require(value, message):
    if not value:
        raise ValueError(message)


def inspect(read):
    def record(name):
        return json.loads(read(name).decode('utf-8-sig'))

    source = record('interaction-product/SOURCE-HOST.json')
    sha = source['Executable']['SHA256'].lower()
    identity = record('interaction/identity.json')
    require(sha == identity['executable_sha256'], 'product identity mismatch')
    verdicts = []
    windows = set()
    for row in record('interaction/results.json'):
        window = row['id']
        if window not in WINDOWS:
            continue
        require(window not in windows, 'duplicate window: '+window)
        windows.add(window)
        attempt = row['directory'].replace('\\','/').rsplit('/', 1)[-1]
        require(attempt.startswith(window+'-') and attempt[len(window)+1:].isdigit(), 'invalid attempt: '+attempt)

        def owned(name):
            member = 'research/'+name
            raw = read('interaction/attempts/'+attempt+'/'+member)
            require(hashlib.sha256(raw).hexdigest() == row['evidence'][member], 'digest mismatch: '+name)
            return raw

        tab = '-profile-font-' not in window
        obs = json.loads(owned(('tabs-' if tab else '')+'selection-observed.json'))
        require(obs['executable_sha256'] == sha and obs['active_renderer'] == WINDOWS[window]
                and obs['tab_host'] is tab and obs['requested_font'] == ('SarasaTermSC Nerd Light' if tab else None),
                'wrong window, renderer, font or executable: '+window)
        cw,ch = obs['cell_pixels']
        for channel in ('messages','system'):
            names = set(CASES) if channel == 'messages' else SYSTEM if tab else set()
            rows = obs.get('resize_press_'+channel, [])
            require({r['case'] for r in rows} == names and len(rows) == len(names), 'incomplete '+window+'/'+channel)
            for r in rows:
                name = r['case']; y, columns = CASES[name]
                label = window+'/'+channel+'/'+name
                stem = ('system-' if channel=='system' else '')+'resize-press-'+name+'-'
                def image(part):
                    return Image.open(io.BytesIO(owned(stem+part+'.png'))).convert('RGB')
                before, after = image('before-release'), image('after-release')
                require(before.size == after.size == (80*cw+2,24*ch+2), label+' geometry')
                def band(i):
                    return before.crop((1,1+i*ch,1+80*cw,1+(i+1)*ch))
                ref = band(y+5)
                require(any(low != high for low,high in ref.getextrema()) and
                        not ImageChops.difference(band(y),ref).getbbox(), label+' initial reference row')
                diff = ImageChops.difference(before, after)
                box = diff.getbbox()
                changed = [x for x in range(80) if diff.crop((1+x*cw,1+y*ch,1+(x+1)*cw,1+(y+1)*ch)).getbbox()]
                confined = box is None or (box[0]>=1 and box[2]<=1+80*cw and box[1]>=1+y*ch and box[3]<=1+(y+1)*ch)
                keep = bool(columns); text = 'EFG' if keep else None
                right = b'' if keep else b'\x1b[<2;14;6M\x1b[<2;14;6m'
                checks = dict(pixels=(confined and changed == list(columns)),
                              recorded_pixels=(changed == r['highlight']),
                              clipboard=(r['clipboard_changed'] is keep and r['right_copy'] == r['shortcut_copy'] == text),
                              held_input=(bytes.fromhex(r['gesture']) == ACK*2),
                              next_right_input=(bytes.fromhex(r['right_wire']) == ACK+right+ACK))
                verdicts.append(dict(window=window, channel=channel, case=name, changed_columns=changed,
                                     right_copy=r['right_copy'], checks=checks, passed=all(checks.values())))
    require(windows == set(WINDOWS) and len(verdicts)==34, 'missing window or gesture')
    return dict(product=source['SourceCommit'], sha256=sha, fixture=identity['fixture_commit'],
                passed=sum(v['passed'] for v in verdicts), total=len(verdicts), cases=verdicts)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path, help='raw interaction-selection ZIP, or its root directory')
    p.add_argument('--json', type=Path)
    args = p.parse_args()
    if args.source.is_dir():
        result = inspect(lambda n: (args.source/n).read_bytes())
    else:
        with ZipFile(args.source) as archive:
            result = inspect(archive.read)
    if args.json:
        args.json.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(f"{result['sha256']}: {result['passed']}/{result['total']} held selections match")
    for v in result['cases']:
        if not v['passed']:
            print(v['window'],v['channel'],v['case'],{k for k,ok in v['checks'].items() if not ok})
    return 0 if result['passed']==result['total'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
