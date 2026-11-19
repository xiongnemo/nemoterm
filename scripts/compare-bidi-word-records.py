"""Read two hosted interaction artifacts; compare recorded cells and copy results."""
import argparse
import io
import json
from pathlib import Path
from zipfile import ZipFile


def read(path):
    with ZipFile(path) as z:
        identity=json.loads(z.read('interaction-product/SOURCE-HOST.json'))
        records={}; pictures={}
        for name in z.namelist():
            if not name.endswith('selection-observed.json'):continue
            result=json.loads(z.read(name))
            if 'bidi_word_messages' not in result:continue
            directory=name.rsplit('/',1)[0];case=directory.split('/')[-2]
            for kind,field in [('message','bidi_word_messages'),('system','bidi_word_system')]:
                for row in result.get(field,[]):
                    width=2 if row['case']=='double-width' else 1
                    assert row['visible_source_indices']==[i for i in (0,3,2,1,4) for _ in range(width)]
                    assert row['wire']=='1b5b306e1b5b306e'
                    key=(case,kind,row['case']);assert key not in records
                    prev=(list(range(80)) if row['case']=='soft-wrap-dots' else [79] if row['case']=='soft-wrap' else [])
                    passed=(row['copied']==row['expected'] and row['highlight']==row['expected_highlight'] and row['previous_row_highlight']==prev)
                    assert row['passed']==passed;records[key]=(row['expected'],row['expected_highlight'],passed)
            if case=='selection-gdi-01':
                for phase in ('source','copied'):
                    pictures[phase]=(result['cell_pixels'],z.read(f'{directory}/system-bidi-word-visual-left-{phase}.png'))
    return identity['Executable']['SHA256'],records,pictures


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('before',type=Path);parser.add_argument('after',type=Path);parser.add_argument('--image',type=Path);args=parser.parse_args()
    old,cases0,pics0=read(args.before);new,cases1,pics1=read(args.after)
    assert old!=new and set(cases0)==set(cases1) and len(cases0)==38
    assert all(cases0[k][:2]==cases1[k][:2] for k in cases0)
    for kind in ('message','system'):
        keys=[k for k in cases0 if k[1]==kind];print(f'{kind} ({len(keys)}): before {sum(cases0[k][2] for k in keys)}, after {sum(cases1[k][2] for k in keys)}')
    if args.image:
        from PIL import Image,ImageDraw
        canvas=Image.new('RGB',(396,130),'white');draw=ImageDraw.Draw(canvas)
        for column,(label,pics) in enumerate([('Before',pics0),('After',pics1)]):
            draw.text((column*198+10,4),label,fill='black')
            for line,phase in enumerate(('source','copied')):
                (cw,ch),png=pics[phase];image=Image.open(io.BytesIO(png));top=1+7*ch
                crop=image.crop((1,top,1+5*cw,top+ch));crop=crop.resize((5*cw*2,ch*2),Image.Resampling.NEAREST)
                canvas.paste(crop,(column*198+80,26+line*52));draw.text((column*198+10,36+line*52),phase,fill='black')
        canvas.save(args.image)

if __name__=='__main__':main()
