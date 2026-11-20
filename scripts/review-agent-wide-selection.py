"""Review matching hosted agent-grid ZIPs offline and crop the selected wide cells."""
import argparse
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw


def background_change(before, after):
    colours = list(before.getpixel((x,y)) for y in range(before.height) for x in range(before.width))
    bg = Counter(colours).most_common(1)[0][0]
    return sum(c == bg and after.getpixel((i % before.width,i // before.width)) != bg
               for i,c in enumerate(colours)) / colours.count(bg)


def review(receipt, surfaces, output):
    previews, records, reports = {}, {}, {}
    with ZipFile(receipt) as z, ZipFile(surfaces) as images:
        for name in ('interaction-product/SOURCE-HOST.json','interaction/identity.json'):
            assert z.read(name) == images.read(name), 'source/fixture mismatch: '+name
        source=json.loads(z.read('interaction-product/SOURCE-HOST.json'))
        ident=json.loads(z.read('interaction/identity.json'))
        assert not ident['fixture_dirty'] and ident['executable_sha256']==source['Executable']['SHA256'].lower()
        cases=json.loads(z.read('interaction/results.json')); assert len(cases)==10
        for case in cases:
            assert case['status']=='passed' and not case['cleanup']['terminated_remaining']
            prefix='interaction/'+case['directory']+'/'
            def verified(archive, path):
                data=archive.read(prefix+path)
                assert sha256(data).hexdigest()==case['evidence'][path],path
                return data
            key,=[k for k in case['evidence'] if k.startswith('research/') and k.endswith('-observed.json')]
            raw=verified(z,key);r=json.loads(raw);wide=r['wide_system_copy']
            left,right=wide['columns'];cw,ch=r['cell'];x,y=r['offset'];y+=ch*wide['row']
            assert wide['copied']==wide['text']=='中文' and (right,wide['down'],wide['up'])==(left+3,left+1,right-1)
            mouse=r['mouse_requests_at_drag']; assert r['completed'] and r['font']=='SarasaTermSC Nerd Light' and mouse['active']
            vt=verified(images,'research/'+r['client']+'-at-drag.vt');assert sha256(vt).hexdigest()==mouse['sha256']
            assert r['native_runtime'] and all(m['exact_frontend_module'] and not m['matched_processes'] and
                                               not m['matched_modules'] for m in r['native_runtime'])
            pair=[];hashes={}
            for stage in ('source','wide-selected'):
                name=key.removesuffix('observed.json')+stage+'.png'; data=verified(images,name)
                im=Image.open(BytesIO(data)).convert('RGB'); box=(x+(left-1)*cw,y,x+(right+2)*cw,y+ch)
                assert 0<=box[0]<box[2]<=im.width and 0<=box[1]<box[3]<=im.height
                pair.append(im.crop(box)); hashes[stage]=sha256(data).hexdigest()
            fractions=[]
            for col in range(6):
                box=(col*cw,0,(col+1)*cw,ch)
                fractions.append(background_change(pair[0].crop(box),pair[1].crop(box)))
            assert max(fractions[0],fractions[5])<=.1 and min(fractions[1:5])>=.5,(case['id'],fractions)
            label=case['id'];reports[label]=dict(copied=wide['copied'],image_sha256=hashes,mouse_mode=mouse['events'][-1],
                                                 pointer_columns=[wide['down'],wide['up']],background_change_by_cell=fractions)
            records[label+'/observed.json']=raw
            if 'shell' not in label and 'visual-order' not in label:previews[r['client'],r['requested_renderer']]=pair
    assert len(reports)==10 and len(previews)==6
    crops=[im for pair in previews.values() for im in pair]; assert len({im.size for im in crops})==1
    w,h=crops[0].size;dx,dy=2*w+22,2*h+6
    picture=Image.new('RGB',(96+4*dx,49+3*dy),'white');pen=ImageDraw.Draw(picture)
    pen.text((8,8),'Physical Shift drag across two wide glyphs (2x screenshot crops)',fill='black')
    for j,label in enumerate(('GDI before','GDI selected','DirectX before','DirectX selected')):pen.text((96+dx*j,28),label,fill='black')
    for i,client in enumerate(('codex','opencode','claude')):
        y=49+i*dy;pen.text((8,y+14),client,fill='black')
        for j,im in enumerate(previews[client,'gdi']+previews[client,'directx']):
            picture.paste(im.resize((2*w,2*h),Image.Resampling.NEAREST),(96+j*dx,y))
    output.mkdir();picture.save(output/'selected.png')
    with ZipFile(output/'observations.zip','x',ZIP_DEFLATED) as archive:
        for name,blob in records.items():archive.writestr(name,blob)
        for name,data in [('review',reports),('source',source),('archives',{p.name:sha256(p.read_bytes()).hexdigest() for p in (receipt,surfaces)})]:
            archive.writestr(name+'.json',json.dumps(data,indent=2).encode())
    print(f"{len(reports)} physical wide-cell copies verified for {source['SourceCommit']}")


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('receipt',type=Path);cli.add_argument('surfaces',type=Path)
    cli.add_argument('--output',type=Path,required=True,help='absent directory to create for the montage and records')
    options=cli.parse_args(); review(options.receipt,options.surfaces,options.output)
