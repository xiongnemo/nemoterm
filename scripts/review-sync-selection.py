"""Read the unmodified hosted synchronization gesture archives and their PNGs."""
import argparse
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile
from PIL import Image, ImageChops

ACK=b'\x1b[0n'
def mode(frozen):return b'\x1b[?2026;'+(b'1' if frozen else b'2')+b'$y\x1b[?1002;1$y\x1b[?1006;1$y'+ACK

GROUPS={'initial':{'live-old','live-new','press-frozen','copy-frozen','right-frozen'}}
GROUPS['copy']=GROUPS['initial']|{'copy-primary','right-primary','right-frozen-paste','right-primary-paste'}
GROUPS['drag']=GROUPS['copy']|{'press-slow','press-rectangle'}

def review(path,generation):
    with ZipFile(path) as z:
        def doc(n):return json.loads(z.read(n).decode('utf-8-sig'))
        exe=doc('build/sync-selection-product/SOURCE-HOST.json');font=doc('build/interaction-dependencies/environment.json')['Font']
        result=dict(artifact=path.name,sha256=sha256(path.read_bytes()).hexdigest(),product=exe['SourceCommit'],exe=exe['Executable']['SHA256'],font=font['Actual'],cases={})
        for n in sorted(name for name in z.namelist() if name.startswith('research/sync-select-') and name.endswith('.json')):
            data=doc(n);engine=data['actual_renderer'];assert engine in (1,3) and data['exe_sha256']==result['exe'] and data['font']==font['Actual']==font['Requested']
            assert data['returncode']==0 and not data['cleanup']['terminated_remaining']
            width,height,cw,ch=data['geometry'];result['renderer']=engine
            def rowbox(y):return (1+3*cw,1+y*ch,1+7*cw,1+(y+1)*ch)
            def shape(img):
                raw=img.tobytes(); pixels=list(zip(raw[0::3],raw[1::3],raw[2::3])); background=Counter(pixels).most_common(1)[0][0];return bytes(p!=background for p in pixels)
            for index,row in enumerate(data['cases']):
                case=row['case'];assert case not in result['cases'];y=4+2*(index%7);frozen=not case.startswith('live');picked=case=='live-new';paste=case.endswith('-paste');want='明月' if picked else '中文'
                def load(label):
                    im=Image.open(BytesIO(z.read(f'research/sync-select-{engine}-{case}-{label}.png'))).convert('RGB');assert im.size==(width,height);return im
                before,at=load('before'),load('gesture');ref=shape(at.crop(rowbox(20 if picked else 18)));other=shape(at.crop(rowbox(18 if picked else 20)))
                flags=dict(visible_at_press=ImageChops.difference(before.crop(rowbox(y)),at.crop(rowbox(y))).getbbox() is None and
                           shape(at.crop(rowbox(y)))==ref!=other and at.getpixel((1+12*cw,1+y*ch))==((16,48,180) if picked else (180,32,16)),
                           clipboard=row['fresh_clipboard'] and row['copied']==want,
                           raw_input=bytes.fromhex(row['gesture_wire'])==((b'\x1b]52;p;TkVX\x07' if 'primary' in case else b'')+mode(frozen)+(want.encode() if paste else b'')+ACK),
                           timing=(row['pre_gesture_ms']<1000 and (row['sample_end_ms']>1120 if case=='press-slow' else (not frozen or row['sample_end_ms']<1000))))
                if 'committed_right_wire' in row:
                    mouse=f'\x1b[<2;7;{y+1}M\x1b[<2;7;{y+1}m'.encode();flags['after_commit']=bytes.fromhex(row['committed_right_wire'])==mode(False)+mouse+ACK
                spans={}
                for label in row.get('held_checks',{}):
                    held=load(label);bounds=ImageChops.difference(at,held).getbbox();spans[label]=bounds
                    flags[label]=(bounds==rowbox(y) and shape(held.crop(rowbox(y)))==ref and row['held_checks'][label]['captured'] and row['first_highlight_ms']<1000)
                if generation=='drag' and case.startswith('press-'):
                    flags['held_frames_complete']=set(spans)==({'held','held-over-deadline'} if case=='press-slow' else {'held'}) and row['post_mode_wire']==mode(False).hex() and 'held_memory' in row
                if 'held_memory' in row:flags['memory']=row['held_memory']['private_ws']<(20_000_000 if engine==1 else 30_000_000)
                result['cases'][case]=dict(passed=all(flags.values()),checks=flags,changed_pixels_bbox=spans,copy=row['copied'],fixture_passed=row['passed'],held_private_ws=row.get('held_memory',{}).get('private_ws'))
        assert set(result['cases'])==GROUPS[generation],(generation,list(result['cases']))
        return result

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('archives',nargs='+',type=Path);cli.add_argument('--output',type=Path);cli.add_argument('--generation',choices=GROUPS,default='drag');cli.add_argument('--expect-commit');args=cli.parse_args()
    reports=[review(archive,args.generation) for archive in args.archives]
    assert {r['renderer'] for r in reports}=={1,3} and len(reports)==2
    assert len({(r['product'],r['exe'],r['font']) for r in reports})==1
    if args.expect_commit:assert reports[0]['product']==args.expect_commit
    if args.output:args.output.write_text(json.dumps(reports,indent=2,ensure_ascii=False),encoding='utf8')
    for group in reports:
        cases=group['cases'];print(group['product'][:8],group['renderer'],len(cases),[k for k,v in cases.items() if not v['passed']]);assert cases
    raise SystemExit(any(not v['passed'] or not v['fixture_passed'] for r in reports for v in r['cases'].values()))
