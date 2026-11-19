"""Compare recorded PNG cells across a tab switch. Opens only two saved Actions archives."""
import argparse
import io
import json
from pathlib import Path
from zipfile import ZipFile
from PIL import Image, ImageChops, ImageDraw


def read(archive, subdir=''):
    directory='interaction/attempts/tab-clipboard-ownership-01/research/tab-clipboard/'+subdir
    with ZipFile(archive) as z:
        result=json.loads(z.read(directory+'result.json'))
        key=result['sha256'];assert json.loads(z.read('interaction-product/SOURCE-HOST.json'))['Executable']['SHA256']==key
        target=result['sessions'][1];width,wx=divmod(target['client_width']-2,target['cols']);height,hy=divmod(target['client_height']-2,target['rows']);assert not (wx or hy)
        def row(name):
            with Image.open(io.BytesIO(z.read(directory+name+'.png'))) as image:
                return image.convert('RGB').crop((1,1+2*height,1+5*width,1+3*height))
        original=row('1-source');rows=[row('interrupted-destination-'+phase) for phase in ('before-up','after-up')]
        masks=[]
        for image in rows:
            diff=ImageChops.difference(original,image).convert('L');mask=''
            for x in range(5):
                zeros=diff.crop((x*width,0,(x+1)*width,height)).histogram()[0];ratio=1-zeros/(width*height)
                mask+='1' if ratio>.5 else '0' if ratio<.1 else '?'
            masks.append(mask)
        return key, target['renderer'], rows, masks


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('before',type=Path);parser.add_argument('after',type=Path);parser.add_argument('--image',type=Path);a=parser.parse_args()
    cases=[read(a.before),read(a.after),read(a.after,'gdi-destination/')]
    assert cases[0][0]!=cases[1][0]==cases[2][0] and [c[1] for c in cases]==[2,2,0]
    labels=('Before / DirectX','After / DirectX','After / GDI');board=Image.new('RGB',(430,126),'white');draw=ImageDraw.Draw(board)
    for i,((digest,renderer,rows,masks),label) in enumerate(zip(cases,labels)):
        print(label,digest,*masks);draw.text((78+116*i,4),label,fill='black')
        for j,im in enumerate(rows):
            draw.text((4,34+49*j),('Before up','After up')[j],fill='black');board.paste(im.resize((im.width*2,im.height*2),Image.Resampling.NEAREST),(78+116*i,25+49*j))
    if a.image:board.save(a.image)


if __name__=='__main__':main()
