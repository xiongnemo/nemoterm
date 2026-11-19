"""Compare held-press erase evidence from two downloaded interaction-selection ZIPs."""
import argparse
import io
import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from PIL import Image, ImageDraw


# Independent expectations for each clipboard and the right-button owner.
SURVIVES = {'erase-ech-neighbour': 'K M', 'erase-protected':'KLM',
            'erase-protected-rect':'K M', 'erase-blank':'  M', 'erase-other-row':'KLM'}
DISCARDS = {'erase-ech','erase-el','erase-ed','erase-rect','erase-selective',
            'erase-selective-rect','erase-wide-trailer'}
ACK = b'\x1b[0n'


def observed_pass(item):
    name = item['case']; text = SURVIVES.get(name); keep = name in SURVIVES
    assert keep or name in DISCARDS
    x,y = item['released']; dx = item['destination']
    assert item['expected']==text and (dx is not None)==keep
    marks = list(range(min(x,dx),max(x,dx)+1)) if keep else []
    wire = b'' if keep else f'\x1b[<2;{x+1};{y+1}M\x1b[<2;{x+1};{y+1}m'.encode()
    return (item['clipboard_changed'] is keep and item['right_copy']==item['shortcut_copy']==text
            and item['highlight']==marks and item['gesture_wire']==(2*ACK).hex()
            and item['right_wire']==(ACK+wire+ACK).hex() and (not keep or item['same_glyph_pixels']))


def read(path):
    rows, crops = {}, {}
    with ZipFile(path) as z:
        manifest = json.loads(z.read('interaction-product/SOURCE-HOST.json'))
        for n in z.namelist():
            if not n.endswith(('/tabs-selection-observed.json','/selection-observed.json')):
                continue
            obs = json.loads(z.read(n)); assert obs['executable_sha256'] == manifest['Executable']['SHA256']
            folder = PurePosixPath(n).parent; window = folder.parent.name
            for key, source in [('horizontal_press','message'),('horizontal_press_system','physical')]:
                for item in obs.get(key, []):
                    case = item['case']
                    if not case.startswith('erase-'): continue
                    identity = (window, source, case)
                    assert identity not in rows
                    assert item['passed'] == observed_pass(item), identity
                    rows[identity] = item
                    if window != 'selection-gdi-01' or source != 'message' or case not in ('erase-ech','erase-protected-rect'): continue
                    cw, ch = obs['cell_pixels']; y = item['pressed'][1]
                    img = Image.open(io.BytesIO(z.read(str(folder / f'{source}-column-{case}.png')))).convert('RGB')
                    crops[case] = img.crop((1,1+y*ch,1+22*cw,1+(y+1)*ch)).resize((44*cw,2*ch),Image.Resampling.NEAREST)
    assert len(rows)==52 and {k[2] for k in rows} == set(SURVIVES) | DISCARDS
    return manifest, rows, crops


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before'); parser.add_argument('after'); parser.add_argument('--figure',type=Path)
    args=parser.parse_args(); old=read(args.before); new=read(args.after)
    if not old[1] or set(old[1]) != set(new[1]): raise ValueError('Missing or different gesture records')
    counts={}
    for identity, after in new[1].items():
        before=old[1][identity]; group=identity[1]; bucket=counts.setdefault(group,[0,0,0]); bucket[2]+=1
        for k in ('block','pressed','released','destination','expected','expected_highlight'):
            assert before[k]==after[k], (identity,k)
        bucket[0]+=before['passed']; bucket[1]+=after['passed']
        if not after['passed'] or identity[0:2]==('selection-gdi-01','message'):
            print(identity, 'right click:',repr(before.get('right_copy')),'->',repr(after.get('right_copy')),
                  'highlight:',before.get('highlight'),'->',after.get('highlight'),'expected:',repr(after['expected']))
    for state in (old,new):print(state[0]['SourceCommit'],state[0]['Executable']['SHA256'])
    print('before passed, after passed, corresponding cases:', counts)
    if args.figure:
        names=['erase-ech','erase-protected-rect']; width,height=old[2][names[0]].size
        canvas=Image.new('RGB',(width*2+40,(height+30)*2+33),'#202020'); draw=ImageDraw.Draw(canvas)
        for j, state in enumerate((old,new)):
            x=10+j*(width+12);draw.text((x,8), ('Before  ' if j==0 else 'After  ')+state[0]['SourceCommit'][:7], fill='white')
            for i, name in enumerate(names):
                y=28+i*(height+30);draw.text((x,y),name,fill='#e0e0e0'); canvas.paste(state[2][name],(x,y+16))
        canvas.save(args.figure)


if __name__=='__main__':main()
