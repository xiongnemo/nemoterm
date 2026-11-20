"""Review the physical shortcuts, original pixels and submitted Unicode for three real clients."""
import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image
from collections import Counter


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def chord(*keys):
    return [[key, True] for key in keys] + [[key, False] for key in reversed(keys)]


def inspect_pixels(source, selected, case):
    first, row, last = case['selection']; ox, oy = case['offset']; cw, ch = case['cell']
    y = oy + row * ch
    need(source.size == selected.size and cw > 0 and ch > 0 and first > 0 and last >= first and
         0 <= y <= source.height-ch and 0 <= ox+(first-1)*cw < ox+(last+2)*cw <= source.width, 'invalid selection rectangle')
    def cells(image):
        return [list(image.crop((ox+x*cw, y, ox+(x+1)*cw, y+ch)).getdata()) for x in range(first-1,last+2)]
    before, after = cells(source), cells(selected)
    bg = Counter(p for tile in before[1:-1] for p in tile).most_common(1)[0][0]
    changed = []
    for old, new in zip(before, after):
        pixels = [b for a,b in zip(old,new) if a == bg]; need(pixels, 'unobservable source background')
        changed.append(sum(p != bg for p in pixels)/len(pixels))
    need(min(changed[1:-1]) >= .5 and max(changed[0],changed[-1]) <= .1, 'highlight or adjacent cell differs')
    return changed


def review(receipt, surfaces):
    def read(z, name): return json.loads(z.read(name).decode('utf-8-sig'))
    result = {}
    with ZipFile(receipt) as summary, ZipFile(surfaces) as z:
        for name in ('interaction/identity.json','interaction/results.json','interaction-product/SOURCE-HOST.json'):
            need(summary.read(name) == z.read(name), 'archives disagree: '+name)
        identity=read(z,'interaction/identity.json'); source=read(z,'interaction-product/SOURCE-HOST.json')
        need(not identity['fixture_dirty'] and identity['executable_sha256'] == source['Executable']['SHA256'] and
             identity['executable_bytes'] == source['Executable']['Bytes'], 'product identity')
        rows=read(z,'interaction/results.json'); cases={r['id']:r for r in rows}; need(len(rows)==len(cases),'duplicate case')
        for client in ('codex','opencode','claude'):
            stable = client=='claude'; expected = 'NEMOTERM_SELECT 中文 '+('q' if stable else 'e')+'\u0301 \uf120 \U000f0001 END'
            for renderer,number in [('gdi',0),('directx',2)]:
                for method in ('keys','default','copy-paste'):
                    suffix = ({'keys':'stable-shortcut','default':'stable-default','copy-paste':'stable-copy-paste'} if stable else
                              {'keys':'system','default':'right-default','copy-paste':'right-copy-paste'})[method]
                    label=f'{client}-{suffix}-{renderer}'; case=cases[label]
                    need(case['status']=='passed' and case['exit_code']==0 and not case['cleanup']['terminated_remaining'] and
                         not case['cleanup']['remaining_processes'], label+': execution/cleanup')
                    def verified(key):
                        data=z.read('interaction/'+case['directory']+'/'+key)
                        need(sha256(data).hexdigest()==case['evidence'][key], label+': '+key); return data
                    key,=[k for k in case['evidence'] if k.startswith('research/') and k.endswith('-observed.json')]
                    obs=json.loads(verified(key)); desktop=obs['desktop']; events=desktop['events']
                    need(obs['completed'] and obs['client']==client and obs['global_input'] and desktop['highlight_while_held'] and
                         obs['session']['renderer']==number and obs['requested_renderer']==renderer and obs['font']=='SarasaTermSC Nerd Light',label+': window')
                    # This slice ends at the Enter that submits the edited prompt. A hidden extra copy or paste changes the sequence.
                    left=events.index(['left',True])-1; submit=events.index([13,True],left)
                    drag=chord(16,'left'); copy=chord(17,16,67); paste=chord(17,16,86); right=chord('right')
                    need(events[left:submit]==drag+{'keys':copy+paste,'default':right+paste,'copy-paste':right}[method],label+': system input')
                    trace=verified('research/'+client+'-at-drag.vt'); mouse=obs['mouse_requests_at_drag']; event=mouse['events'][-1]
                    seq=bytes.fromhex(event['seq']); need(sha256(trace).hexdigest()==mouse['sha256'] and mouse['active'] and event['active'] and
                         event['mode'] in (9,1000,1001,1002,1003) and trace[event['offset']:].startswith(seq) and seq.endswith(b'h'),label+': application mouse tracking')
                    if method!='keys':
                        click=obs['right_click']; need(click['mode']==method and click['setting_written']==(method=='copy-paste') and
                            click['modifiers_released'] and click['clipboard_before']!=click['clipboard_after'] and
                            click['composer_before_paste_key']==('prefix-only' if method=='default' else 'with-selection'),label+': right click')
                    else: need('right_click' not in obs,label+': shortcut')
                    prompt_hash=sha256(('NEMOTERM_SUBMIT '+expected).encode()).hexdigest(); http=obs['http_receipt']
                    need(obs['copied']==expected and expected in obs['source_line'] and http['selection_received'] and
                         http['selected_text_occurrences']==1 and http['fixture_prompt_hashes']==[prompt_hash],label+': clipboard/submission')
                    need(obs['native_runtime'] and all(r['exact_frontend_module'] and not r['matched_modules'] and not r['matched_processes']
                         for r in obs['native_runtime']),label+': runtime observations')
                    base=key.removesuffix('observed.json'); imgs=[]; hashes=[]
                    for stage in ('source','selected'):
                        name=base+stage+'.png'; data=verified(name); hashes.append(sha256(data).hexdigest())
                        with Image.open(BytesIO(data)) as im: imgs.append(im.convert('RGB'))
                    result[label] = dict(mouse_mode=event['mode'],foreground_gesture=method,
                        background_change=inspect_pixels(*imgs,obs),prompt_sha256=prompt_hash,source_selected_png=hashes)
    return dict(source=source['SourceCommit'],executable=source['Executable'],fixture=identity['fixture_commit'],cases=result)


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__); cli.add_argument('receipt',type=Path);cli.add_argument('surfaces',type=Path);cli.add_argument('--output',required=True,type=Path)
    args=cli.parse_args(); record=review(args.receipt,args.surfaces)
    args.output.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8'); print(f"Verified {len(record['cases'])} physical clipboard bindings on {record['source']}")
