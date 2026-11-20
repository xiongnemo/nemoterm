"""Compare existing hosted selection PNGs and Windows clipboard receipts (needs Pillow)."""
import argparse
import hashlib
import io
import json
from zipfile import ZipFile

from PIL import Image, ImageChops


CASES = {'normal-control': (36, 'WXYZOFFSCREEN'), 'double-width': (72, 'WXYZ'),
         'upper-half-reverse': (72, 'WXYZ'), 'lower-half-spaces': (72, 'W')}
WINDOWS = {'selection-gdi': 1, 'selection-directx': 3,
           'selection-profile-font-gdi': 1, 'selection-profile-font-directx': 3}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_archive(path):
    verdicts = {}
    with ZipFile(path) as z:
        def record(name):
            return json.loads(z.read(name).decode('utf-8-sig'))

        sha = record('interaction-product/SOURCE-HOST.json')['Executable']['SHA256'].lower()
        for attempt in record('interaction/results.json'):
            window = attempt['id']
            if window not in WINDOWS:
                continue
            tab = '-profile-font-' not in window
            directory = attempt['directory'].replace('\\', '/').rsplit('/', 1)[-1]
            require(directory.startswith(window+'-') and directory[len(window)+1:].isdigit(), window)

            def read(name):
                member = 'research/'+name
                data = z.read('interaction/attempts/'+directory+'/'+member)
                require(hashlib.sha256(data).hexdigest()==attempt['evidence'][member], name+' digest differs')
                return data

            obs = json.loads(read(('tabs-' if tab else '')+'selection-observed.json'))
            require(obs['executable_sha256']==sha and obs['active_renderer']==WINDOWS[window]
                    and obs['tab_host']==tab and obs['requested_font']==('SarasaTermSC Nerd Light' if tab else None), window)
            cw,ch = obs['cell_pixels']
            for field, prefix, names in [('messages','',set(CASES)), ('system','system-',{'double-width'} if tab else set())]:
                records = obs.get('scaled_copy_'+field, [])
                require(len(records)==len(names) and {r['case'] for r in records}==names, window+'/'+field+' inventory')
                for r in records:
                    case = r['case']; key = (window, field, case)
                    require(key not in verdicts, str(key)+' duplicate')
                    stem = prefix+'scaled-copy-'+case+'-'
                    def image(name):
                        return Image.open(io.BytesIO(read(stem+name+'.png'))).convert('RGB')
                    before, after = image('source'), image('marked')
                    require(before.size==after.size==(80*cw+2, 24*ch+2), str(key)+' geometry')
                    diff = ImageChops.difference(before, after)
                    changed = {}
                    for y in range(24):
                        cols = [x for x in range(80) if diff.crop((1+x*cw, 1+y*ch, 1+(x+1)*cw, 1+(y+1)*ch)).getbbox()]
                        if cols:
                            changed[y] = cols
                    # These are the fixture's authored screen coordinates. Do not
                    # derive the expected positions from the observed highlight.
                    y = 5 if case in ('normal-control','upper-half-reverse') else 13
                    left, text = CASES[case]
                    def line(row):
                        return before.crop((1, 1+row*ch, 1+80*cw, 1+(row+1)*ch))
                    require(not ImageChops.difference(line(y), line(y+3)).getbbox(), str(key)+' differs from reference row')
                    require(changed=={y:list(range(left,80)),y+1:[0,1,2]}, str(key)+' unexpected highlighted pixels')
                    require(bytes.fromhex(r['raw_input'])==b'\x1b[0n'*2, str(key)+' input forwarded')
                    verdicts[key] = r['copied']==text+'\r\nEND'
        require(len(verdicts)==18, 'incomplete window inventory')
        return sha,verdicts


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before'); parser.add_argument('after'); args=parser.parse_args()
    older, first = read_archive(args.before)
    newer, last = read_archive(args.after)
    require(older!=newer and first.keys()==last.keys(), 'expected two different executables and identical case inventories')
    for sha,cases in [(older,first),(newer,last)]:
        print(f'{sha}: {sum(cases.values())}/{len(cases)} clipboard matches; all source rows, highlights and raw input matched')
    raise SystemExit(0 if all(last.values()) else 1)
