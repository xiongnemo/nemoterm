"""Review original screenshots and provider receipts from a hosted agents-grid run without opening a terminal."""
import argparse
from collections import Counter
from hashlib import sha256
import io
import json
from pathlib import Path
from zipfile import ZipFile
from PIL import Image, ImageDraw

STAGES=('before-backspace','one-backspace','after-backspace')


def review(receipt,surfaces,output):
    reports={}; strips=[]
    with ZipFile(receipt) as small, ZipFile(surfaces) as big:
        for name in ('interaction/identity.json','interaction/results.json','interaction-product/SOURCE-HOST.json'):
            assert small.read(name)==big.read(name),name
        ident=json.loads(small.read('interaction/identity.json')); product=json.loads(small.read('interaction-product/SOURCE-HOST.json'))
        assert not ident['fixture_dirty'] and ident['executable_sha256']==product['Executable']['SHA256']
        cases=json.loads(small.read('interaction/results.json')); assert len(cases)==10
        for case in cases:
            prefix='interaction/'+case['directory']+'/'
            def get(z,k):
                b=z.read(prefix+k); assert sha256(b).hexdigest()==case['evidence'][k],k
                return b
            k,=[k for k in case['evidence'] if k.startswith('research/') and k.endswith('-observed.json')]; r=json.loads(get(small,k))
            assert case['status']=='passed' and not case['cleanup']['terminated_remaining'] and r['completed']
            assert r['child']['terminal_sha256']==ident['executable_sha256'] and r['child']['client_sha256']==ident['clients'][r['client']]['sha256']
            assert r['wide_system_copy']['copied']=='中文' and r['mouse_requests_at_drag']['active']
            m=r['close_cancel']; e=m['backspace_edit'];assert m['clipboard_intact'] and e['corrected'] and e['typed']==m['typed_prefix']+'xx'
            assert e['clipboard_before']==e['clipboard_after'] and e['capture']['pid']==r['child']['pid'] and e['capture']['closed']
            assert not e['capture']['desktop_dc'] and not e['capture']['wm_print'] and not e['capture']['activation']
            assert r['http_receipt']['selected_text_occurrences']==1 and r['http_receipt']['selection_received']
            assert r['http_receipt']['fixture_prompt_hashes']==[sha256((m['typed_prefix']+r['copied']).encode()).hexdigest()]
            cw,ch=e['cell']; ox,oy=e['origin']; x=ox+e['column']*cw;y=oy+e['row']*ch
            masks=[]; stages={}; tiles=[]
            for stage in STAGES:
                f,=[s for s in r['screenshots'] if s.endswith('-composer-'+stage+'.png')]
                blob=get(big,'research/'+f);im=Image.open(io.BytesIO(blob)).convert('RGB');assert 0<=x and x+2*cw<=im.width and 0<=y and y+ch<=im.height
                pair=[]
                for i in range(2):
                    cell=im.crop((x+i*cw+1,y+2,x+(i+1)*cw-1,y+ch-3));pixels=list(cell.getdata());bg=Counter(pixels).most_common(1)[0][0]
                    pair.append(bytes(max(abs(p-q) for p,q in zip(pixel,bg))>24 for pixel in pixels))
                hashes=[sha256(s).hexdigest() for s in pair];assert hashes==e['frames'][stage]['mask_sha256']
                stages[stage]=dict(image_sha256=sha256(blob).hexdigest(),ink=[sum(s) for s in pair],mask_sha256=hashes)
                assert stages[stage]['ink']==e['frames'][stage]['ink'];masks.append(pair);tiles.append(im.crop((x-4*cw,y,x+3*cw,y+ch)))
            a,b,c=masks;assert sum(a[0])>=5 and a[0]==a[1]==b[0] and not any(b[1]) and not any(c[0]) and not any(c[1]);strips.append((case['id'].removeprefix('agent-grid-'),tiles))
            reports[case['id']]=dict(stages=stages,submitted=r['http_receipt']['fixture_prompt_hashes'][0],wide_copy=r['wide_system_copy']['copied'])
    assert len(reports)==10
    out=dict(product=product['SourceCommit'],executable_sha256=ident['executable_sha256'],fixture=ident['fixture_commit'],cases=reports,
             archive_sha256={p.name:sha256(p.read_bytes()).hexdigest() for p in (receipt,surfaces)})
    output.mkdir();(output/'composition.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf8')
    sheet=Image.new('RGB',(580,35+len(strips)*48),'#f4f4f4');draw=ImageDraw.Draw(sheet)
    for i,title in enumerate(('typed xx','one Backspace','two Backspaces')):draw.text((182+i*130,10),title,fill='#161616')
    for index,(name,parts) in enumerate(strips):
        ypos=32+index*48;draw.text((8,ypos+14),name,fill='#161616')
        for i,im in enumerate(parts):sheet.paste(im.resize((im.width*2,im.height*2),Image.Resampling.NEAREST),(182+i*130,ypos))
    sheet.save(output/'composition.png');print('Verified 30 presented frames and 10 provider receipts:',ident['executable_sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('receipt',type=Path);p.add_argument('surfaces',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();review(args.receipt,args.surfaces,args.output)
