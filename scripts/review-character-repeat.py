"""Independently inspect the four displayed cells after one coalesced Unicode message."""
import argparse
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile
from PIL import Image


STAGES = ('repeated-han', 'one-han', 'removed-han')
CLIENTS = ('codex', 'opencode', 'claude', 'claude-shell', 'claude-visual-order')
FONT = 'SarasaTermSC Nerd Light'


def require(ok, description):
    if not ok:
        raise ValueError(description)


def half_masks(png, edit):
    cw, ch = edit['cell']; ox, oy = edit['origin']
    x = ox + edit['column']*cw; y = oy + edit['row']*ch
    with Image.open(BytesIO(png)) as source:
        require(source.format == 'PNG' and cw > 2 and ch > 5 and 0 <= x <= source.width-4*cw
                and 0 <= y <= source.height-ch, 'frame does not contain four whole cells')
        image = source.convert('RGB')
    masks = []
    for col in range(4):
        left = x+col*cw
        pixels = list(image.crop((left+1, y+2, left+cw-1, y+ch-3)).getdata())
        bg = Counter(pixels).most_common(1)[0][0]
        masks.append(bytes(any(abs(a-b)>24 for a,b in zip(pixel,bg)) for pixel in pixels))
    return masks


def review(receipt, surfaces):
    with ZipFile(receipt) as small, ZipFile(surfaces) as big:
        def common(key):
            blob = small.read(key); require(blob == big.read(key), key+' differs between archives')
            return json.loads(blob.decode('utf-8-sig'))
        ident = common('interaction/identity.json'); source = common('interaction-product/SOURCE-HOST.json')
        cases = common('interaction/results.json'); exe = source['Executable']
        require((exe['SHA256'],exe['Bytes']) == (ident['executable_sha256'],ident['executable_bytes'])
                and not ident['fixture_dirty'] and ident['font']==FONT, 'executable, fixture or font identity')
        wanted = {f'agent-grid-{v}-{r}':(v.split('-')[0],r) for v in CLIENTS for r in ('gdi','directx')}
        require(len(cases)==len(wanted) and {c['id'] for c in cases}==wanted.keys(), 'case inventory')
        rows = {}
        for c in cases:
            name=c['id']; client,renderer=wanted[name]
            def member(archive, key):
                blob=archive.read('interaction/'+c['directory']+'/'+key)
                require(sha256(blob).hexdigest()==c['evidence'][key],name+' '+key+' digest differs')
                return blob
            observed,=[k for k in c['evidence'] if k.startswith('research/') and k.endswith('-observed.json')]
            r=json.loads(member(small,observed)); child=r['child']; seat=r['session']
            require(child['terminal_sha256']==exe['SHA256'] and child['client_sha256']==ident['clients'][client]['sha256']
                    and r['client']==client and r['requested_renderer']==renderer and seat['renderer']=={'gdi':0,'directx':2}[renderer]
                    and r['global_input'] and r['font']==FONT,name+' window identity')
            edit=r.get('close_cancel',{}).get('backspace_edit',{}); repeat=edit.get('character_repeat',{})
            cap=edit.get('capture',{}); report=rows[name]=dict(original_status=c['status'],counts=repeat.get('counts'),frames={},verified=False)
            if not repeat: continue  # An older or interrupted fixture supplies no repeat proof.
            require((repeat['message'],repeat['scalar'],repeat['count'])==('WM_CHAR',0x4e2d,2),name+' input')
            require(cap['pid']==child['pid'] and cap['hwnd']==seat['hwnd'] and cap['closed'] and not cap['activation']
                    and not cap['wm_print'] and not cap['desktop_dc'] and bool(cap.get('surface'))==(renderer=='directx'),name+' capture source')
            masks={}
            for fn in r['screenshots']:
                marker='-composer-'
                if marker not in fn or not fn.endswith('.png'): continue
                stage=fn.rsplit(marker,1)[1][:-4]
                if stage not in STAGES and not (stage.startswith('unmatched-') and 'han' in stage): continue
                require(stage not in masks,name+' duplicate frame '+stage)
                png=member(big,'research/'+fn); cells=masks[stage]=half_masks(png,edit)
                report['frames'][stage]=dict(png_sha256=sha256(png).hexdigest(),cell_ink=[sum(m) for m in cells],
                                             cell_mask_sha256=[sha256(m).hexdigest() for m in cells])
            if not all(s in masks for s in STAGES): continue
            two,one,none=(masks[s] for s in STAGES)
            prompt=r.get('http_receipt',{}); prefix=r['close_cancel']['typed_prefix']
            report['verified']=(min(map(sum,two[:2]))>=5 and two[:2]==two[2:]==one[:2] and not any(map(any,one[2:]+none))
                                and repeat.get('counts')==[2,1,0] and r['wide_system_copy']['copied']=='中文' and prompt.get('selection_received')
                                and prompt['selected_text_occurrences']==1
                                and prompt['fixture_prompt_hashes']==[sha256((prefix+r['copied']).encode()).hexdigest()]
                                and r['completed'] and c['status']=='passed' and not c['cleanup']['terminated_remaining'])
    return dict(executable=exe,product=source['SourceCommit'],fixture=ident['fixture_commit'],cases=rows,
                verified=sum(row['verified'] for row in rows.values()),expected=len(wanted))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('receipt','surfaces','output'): parser.add_argument(name,type=Path)
    args=parser.parse_args(); report=review(args.receipt,args.surfaces)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(f"Repeated Han glyphs: {report['verified']}/{report['expected']} on {report['executable']['SHA256']}")
    raise SystemExit(0 if report['verified']==report['expected'] else 1)
