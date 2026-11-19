"""Crop original hosted Claude windows and verify glyph tiles against their archived receipts."""
import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile
from PIL import Image, ImageDraw, ImageFont


def sha(data):
    return hashlib.sha256(data).hexdigest()


def tiles(archive, accepted_archives, product, order, copied):
    data = archive.read_bytes()
    assert sha(data) in accepted_archives
    with ZipFile(io.BytesIO(data)) as z:
        name, = [n for n in z.namelist() if '/agent-grid-claude-gdi-01/' in n and n.endswith('gdi-system-observed.json')]
        obs = json.loads(z.read(name)); w = obs['bidi_system_copy']
        assert obs['child']['terminal_sha256'] == product and not obs['client_visual_order']
        assert w['copied'] == copied and w['actual_digests'] == [w['reference_digests'][j] for j in order]
        assert obs['bidi_highlight']['cells'] == 2 and min(obs['bidi_highlight']['guard_ratios']) >= .9
        cw,ch = obs['cell']; ox,oy = obs['offset']; x = w['columns'][0]; y = oy + ch*w['row']
        def get(label):
            return Image.open(io.BytesIO(z.read(name.removesuffix('observed.json')+label+'.png'))).convert('RGB')
        src = get('bidi-source'); sel = get('bidi-selected')
        def crop(pic, c, n=1):return pic.crop((ox+c*cw,y,ox+(c+n)*cw,y+ch))
        assert [sha(crop(src,x+i).tobytes()) for i in (1,2,3)] == w['actual_digests']
        assert [sha(crop(src,c).tobytes()) for c in w['reference_columns']] == w['reference_digests']
        assert all(crop(src,x+i).tobytes()!=crop(sel,x+i).tobytes() for i in (0,1))
        return [crop(src,x,5),crop(sel,x,5)]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('before','after','output'):p.add_argument(key,type=Path)
    args=p.parse_args()
    before=tiles(args.before,{'40d1331cf4547c8fa9a7341dcaf03ea3d6f5847a0fced9d040fa5b2922b16a18',
                              'ddf2d2efcf49837bf3f352c5240dcccc755b92a3a0f50f3ea265e974ffcfbbba'},
                 '3785ec282c588ee7277a916323223a9334ee93ecb07cf642721b2215d898e225',[2,1,0],'A\u05d0')
    after=tiles(args.after,{'3068706c0ac8e4dccd3b2e76e5286bb56d552c09c23e662904491d5c31fcaba6',
                            '2c8739c8afb1bc2e1e0446995abd81102f567621a02e403671796094d1efa751'},
                'c149c2bc3a3a2e0d2594ae2a239520af15a47bbb5c4d49c4daae3dc998bf64ba',[0,1,2],'A\u05d2\u05b0')
    canvas=Image.new('RGB',(610,230),'#ffffff');draw=ImageDraw.Draw(canvas);font=ImageFont.load_default(size=16)
    def text(x,y,s):draw.text((x,y),s,fill='#182532',font=font)
    text(8,8,'GDI / Sarasa Light');text(180,8,'Before drag');text(380,8,'Shift drag: two cells')
    for row,(label,copy,pair) in enumerate([('6ee2996','A + alef',before),('7ec651d','A + gimel + sheva',after)]):
        y=36+96*row;text(8,y+15,label);text(8,y+40,copy)
        for col,img in enumerate(pair):canvas.paste(img.resize((img.width*4,img.height*4),Image.Resampling.NEAREST),(180+200*col,y))
    canvas.save(args.output)


if __name__=='__main__':main()
