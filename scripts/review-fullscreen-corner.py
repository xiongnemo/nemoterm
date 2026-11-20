"""Independently check the fullscreen corner gesture from the Windows observers' original data."""
import argparse
import hashlib
import io
import json
import re
from pathlib import Path
from zipfile import ZipFile
from PIL import Image, ImageChops

ACK=b'\x1b[0n'
TEXT='A\u4e2dZ'

def review(path, engine, renderer, commit):
    with ZipFile(path) as z:
        def data(n):return json.loads(z.read(n).decode('utf-8-sig'))
        manifest=data('build/sync-selection-product/SOURCE-HOST.json');font=data('build/interaction-dependencies/environment.json')['Font']
        assert manifest['SourceCommit']==commit and font['Requested']==font['Actual']=='SarasaTermSC Nerd Light'
        digest=manifest['Executable']['SHA256'];rows={}
        for place in ('standalone','top','bottom','left','right'):
            folder='research/fullscreen-corner-'+renderer+('' if place=='standalone' else '-'+place)+'/'
            row=rows[place]={}
            try:
                r=data(folder+'result.json');row['recorded_error']=r.get('error');row['menu_at_shift_down']=r.get('shift_down',{}).get('menu')
                assert r['sha256']==digest and r['font']==font['Actual'] and r['renderer']==engine and r['placement']==place
                assert r['returncode']==0 and r['passed'] and not r['cleanup']['terminated_remaining']
                xt,yt=r['pane_origin'];assert (xt>0 if place=='left' else xt==0) and (yt>0 if place=='top' else yt==0)
                mouse=re.fullmatch(rb'\x1b\[6;(\d+);(\d+)t'+re.escape(ACK+b'\x1b[<0;4;1M\x1b[<0;4;1m'+ACK),bytes.fromhex(r['nearby_wire']));assert mouse
                ch,cw=map(int,mouse.groups());assert ch>0 and cw>0
                if place=='standalone':assert r['plain_down']['menu'] and bytes.fromhex(r['plain_wire'])==ACK*2
                assert r['shift_down']['terminal_capture'] and not r['shift_down']['menu'] and r['clipboard']==TEXT
                assert bytes.fromhex(r['shift_wire'])==ACK+b'\x1b[200~'+TEXT.encode()+b'\x1b[201~'+ACK
                before,after=(Image.open(io.BytesIO(z.read(folder+n+'.png'))).convert('RGB') for n in ('before','selected'))
                assert before.size==after.size;diff=ImageChops.difference(before,after)
                # Derive the highlighted area from two captured PNGs rather than the observer's verdict.
                bounds=diff.getbbox();assert bounds and bounds==tuple(r['ink_box']),bounds
                x,y,x1,y1=bounds;assert (x1-x,y1-y)==(4*cw,ch) and before.width>=x1+cw
                selected_bg=after.getpixel((x,y));assert before.getpixel((x,y))==(24,64,96) and selected_bg!=(24,64,96)
                # Preserve all three glyphs. The wide middle glyph may have an empty half,
                # so compare its two cells as a single ink mask, also leaving ! untouched.
                masks=[]
                for start,stop in ((0,1),(1,3),(3,4)):
                    box=(x+cw*start,y,x+cw*stop,y1)
                    def ink(im,bg):
                        raw=im.crop(box).tobytes();return bytes(raw[i:i+3]!=bytes(bg) for i in range(0,len(raw),3))
                    a,b=ink(before,(24,64,96)),ink(after,selected_bg);assert any(a) and any(b)
                    # Preserve both masks even when font antialiasing changes a few edge pixels.
                    common=sum(i&j for i,j in zip(a,b));union=sum(i|j for i,j in zip(a,b));masks.append([common,union])
                row.update(bounds=bounds,mask_intersections_and_unions=masks,passed=all(4*i>=3*n for i,n in masks))
            except (AssertionError, KeyError, ValueError) as e:row.update(passed=False,error=repr(e))
        return dict(archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),exe_sha256=digest,product=commit,renderer=renderer,cases=rows)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--commit',required=True);p.add_argument('--output',required=True,type=Path);p.add_argument('gdi',type=Path);p.add_argument('directx',type=Path);args=p.parse_args()
    reports=[review(args.gdi,1,'gdi',args.commit),review(args.directx,3,'directx',args.commit)];assert reports[0]['exe_sha256']==reports[1]['exe_sha256']
    args.output.write_text(json.dumps(reports,indent=2),encoding='utf-8')
    for report in reports:print(report['renderer'],{k:r['passed'] for k,r in report['cases'].items()})
    raise SystemExit(any(not row['passed'] for r in reports for row in r['cases'].values()))
