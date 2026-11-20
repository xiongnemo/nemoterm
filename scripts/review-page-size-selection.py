"""Read two GitHub column-modes ZIPs and compare the actual page-size gesture evidence."""
import argparse
import io
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageChops


INITIAL = (80, 24)
CASES = {
    'lines-same': ('24t', INITIAL), 'rows-same': ('24*|', INITIAL), 'cols-same': ('80$|', INITIAL),
    'lines-grow': ('28t', (80, 28)), 'rows-grow': ('28*|', (80, 28)), 'cols-grow': ('86$|', (86, 24)),
    'lines-denied': ('28t', INITIAL), 'rows-denied': ('28*|', INITIAL), 'cols-denied': ('86$|', INITIAL),
    'lines-standalone': ('28t', (80, 28)), 'rows-standalone': ('28*|', (80, 28)),
    'cols-standalone': ('86$|', (86, 24)), 'cols-drop-glyph': ('72$|', (72, 24)),
    'xtwinops-control': ('8;27;84t', (84, 27)),
}
ACK = b'\x1b[0n'


def review(archive, gpu):
    def read(name): return json.loads(archive.read(name).decode('utf-8-sig'))
    source = read('build/column-product/SOURCE-HOST.json'); sha = source['Executable']['SHA256'].lower()
    folder = f'research/column-mode-page-{gpu}-'; results = {}
    def image(case, stage): return Image.open(io.BytesIO(archive.read(folder+case+'-'+stage+'.png'))).convert('RGB')
    def band(frame, cw, ch): return frame.crop((1+cw, 1+3*ch, 1+7*cw, 1+4*ch))
    def identical(a,b): return a.size == b.size and not ImageChops.difference(a,b).getbbox()
    for tag,(op,(cols,rows)) in CASES.items():
        rec=read(folder+tag+'-result.json'); obs=read(folder+tag+'-observed.json')
        assert rec['executable_sha256']==obs['executable_sha256']==sha
        assert rec['requested_font']==obs['requested_font']=='SarasaTermSC Nerd Light'
        assert rec['renderer']=={'gdi':1,'directx':3}[gpu] and rec['command']==op
        assert rec['tabbed']==bool(obs['profile_values']['NemoTabs'])==(not tag.endswith('standalone'))
        assert rec['denied']==bool(obs['profile_values']['NoRemoteResize'])==tag.endswith('denied')
        assert obs['completed'] and not obs['cleanup']['remaining_processes'] and not obs['cleanup']['terminated_remaining']
        before=image(tag,'drawn'); after=image(tag,'after'); cw,ch=rec['cell']; assert before.size==(2+80*cw,2+24*ch)
        keep=tag!='cols-drop-glyph'; expected='A中Z' if keep else None
        marked=[x for x in range((after.width-2)//cw) if after.getpixel((2+x*cw,2+3*ch))==(34,51,85)]
        text_pixels=True
        if keep:
            ref='lines-standalone' if tag.endswith('standalone') else 'cols-same'
            reference=image(ref,'selected'); target=band(reference,cw,ch); normal=band(before,cw,ch)
            assert not identical(normal,target) and identical(normal,band(image(ref,'drawn'),cw,ch))
            text_pixels=identical(band(after,cw,ch),target)
        reply=f'\x1b[8;{rows};{cols}t'.encode();raw_right=b'' if keep else b'\x1b[<2;9;4M\x1b[<2;9;4m'
        checks=dict(grid=rec['child_grid']==[cols,rows] and rec['client_pixels']==list(after.size)==[cols*cw+2,rows*ch+2],
                    vt=bytes.fromhex(rec['vt_grid_wire'])==reply, mouse=bytes.fromhex(rec['gesture_wire'])==reply+ACK+b'7',
                    highlight=marked==rec['after']==([2,3,4,5] if keep else []), text_pixels=text_pixels,
                    text=rec['shortcut_copy']==rec['right_copy']==expected, shortcut=bytes.fromhex(rec['copy_wire'])==ACK+b'8',
                    right_button=bytes.fromhex(rec['right_wire'])==ACK+raw_right+b'9')
        results[tag]=dict(passed=all(checks.values()),checks=checks,grid=rec['child_grid'],highlight=marked,copied=rec['right_copy'])
    return dict(commit=source['SourceCommit'],sha256=sha,renderer=gpu,passed=sum(v['passed'] for v in results.values()),total=len(results),cases=results)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('gdi',type=Path);p.add_argument('directx',type=Path);p.add_argument('--json',type=Path);a=p.parse_args();rec={}
    for gpu in ('gdi','directx'):
        with ZipFile(getattr(a,gpu)) as z:rec[gpu]=review(z,gpu)
    assert rec['gdi']['sha256']==rec['directx']['sha256'];ok=sum(x['passed'] for x in rec.values());total=sum(x['total'] for x in rec.values())
    if a.json:a.json.write_text(json.dumps(rec,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(rec['gdi']['sha256'],str(ok)+'/'+str(total));raise SystemExit(ok!=total)
