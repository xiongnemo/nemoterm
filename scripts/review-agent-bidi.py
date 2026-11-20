"""Recover the selected physical cells from saved agent window frames and follow the text to the provider."""
import argparse
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image


FONT = 'SarasaTermSC Nerd Light'
REFS = ('גְ', 'ב', 'א')  # Isolated, labelled controls in the recorded provider text
CLIENTS = ('codex', 'claude', 'claude-shell', 'claude-visual-order', 'opencode')


def check(ok, message):
    if not ok:
        raise ValueError(message)


def one(items):
    item, = items
    return item


def digest(data):
    return sha256(data).hexdigest()


def pixels(png, row, positions, origin, cell):
    ox, oy = origin; cw, ch = cell
    check(cw > 2 and ch > 5, 'invalid cell size')
    with Image.open(BytesIO(png)) as source:
        check(source.format == 'PNG', 'expected original PNG')
        im = source.convert('RGB')
    cells = []
    for col in positions:
        x, y = ox + col*cw, oy + row*ch
        check(0 <= x <= im.width-cw and 0 <= y <= im.height-ch, 'cell outside frame')
        cells.append(list(im.crop((x, y, x+cw, y+ch)).getdata()))
    return cells


def ink(tile):
    bg = Counter(tile).most_common(1)[0][0]
    return bytes(any(abs(a-b)>24 for a,b in zip(p,bg)) for p in tile)


def inspect_stage(member, meta, stage, stem, reverse, wire):
    a = stage['bidi_system_copy']; x, tail = a['columns']; row = a['row']
    check(tail == x+1 and a['reference_columns'] == [x+7,x+11,x+15], 'unexpected reference geometry')
    check([a['start'],a['end']] == ([tail,x] if reverse else [x,tail]), 'wrong drag direction')
    emitted = one(v for v in ('AאבגְZ','AגְבאZ') if v.encode() in wire)
    check(emitted == a['emitted'], 'recorded client byte order differs')
    def read_frame(suffix, positions):
        data = member(stem+suffix+'.png')
        return pixels(data,row,positions,meta['offset'],meta['cell']),digest(data)
    src, source_hash = read_frame('source', [x-1,x,x+1,x+2,x+3,*a['reference_columns']])
    sel, selected_hash = read_frame('selected', [x-1,x,x+1,x+2])
    refs = [ink(tile) for tile in src[5:]]
    check(all(any(mask) for mask in refs) and len(set(refs))==3, 'isolated Hebrew controls are blank or indistinguishable')
    order = [refs.index(ink(tile)) for tile in src[2:5]]
    check(order == [0,1,2], 'physical run differs from the intended provider display')
    # Count only former background pixels. Both selected cells must acquire the
    # same new colour and the two neighbouring cells must keep their own colour.
    pairs = []
    for before, after in zip(src[:4],sel):
        bg = Counter(before).most_common(1)[0][0]
        pairs.append((bg,[q for p,q in zip(before,after) if p == bg]))
    chosen = Counter(pairs[1][1]+pairs[2][1]).most_common(1)[0][0]
    ratios = [v.count(chosen if i in (1,2) else bg)/len(v) for i,(bg,v) in enumerate(pairs)]
    check(all(chosen != bg for bg,_ in pairs[1:3]) and min(ratios[1:3]) >= .8 and min(ratios[::3]) >= .9,
          'highlight or adjacent guard did not match: '+str(ratios))
    copied = 'A'+REFS[order[0]]
    check(copied == a['copied'], 'clipboard differs from the two physical cells')
    return dict(row=row,columns=[x,tail],direction='reverse' if reverse else 'forward',wire_sha256=digest(wire),
                source_png_sha256=source_hash,selected_png_sha256=selected_hash,emitted=emitted,physical_order=order,
                clipboard=copied,codepoints=[f'U+{ord(ch):04X}' for ch in copied],background_match=ratios)


def prefix_at_digest(full, at, expected):
    # Writes after the second drag are in the same final stream. Recover the exact
    # earlier prefix by its saved digest instead of treating later bytes as evidence.
    check(len(full)-at <= 4*1024*1024, 'VT prefix search exceeds bounded review size')
    run = sha256(full[:at])
    if run.hexdigest() == expected: return full[:at]
    for end in range(at+1, len(full)+1):
        run.update(full[end-1:end])
        if run.hexdigest() == expected: return full[:end]
    raise ValueError('reply-time VT snapshot is absent from the saved stream')


def review(receipt, surfaces):
    with ZipFile(receipt) as small, ZipFile(surfaces) as big:
        def shared(key):
            b = small.read(key); check(b == big.read(key),key+' differs between archives')
            return json.loads(b.decode('utf-8-sig'))
        ident = shared('interaction/identity.json'); source = shared('interaction-product/SOURCE-HOST.json')
        cases = shared('interaction/results.json'); exe = source['Executable']
        check((exe['SHA256'],exe['Bytes'])==(ident['executable_sha256'],ident['executable_bytes']) and
              not ident['fixture_dirty'] and ident['font']==FONT, 'product, fixture or font identity')
        wanted = {f'agent-grid-{v}-{r}':(v.split('-')[0],r) for v in CLIENTS for r in ('gdi','directx')}
        check(len(cases)==len(wanted) and {c['id'] for c in cases}==wanted.keys(), 'unexpected cases')
        rows = {}
        for c in cases:
            name = c['id']; client,renderer = wanted[name]; ev = c['evidence']; base = 'interaction/'+c['directory']+'/'
            row = rows[name] = dict(original_status=c['status'],stages={},verified=False)
            def read(archive,k):
                b = archive.read(base+k); check(digest(b)==ev[k],k+' digest differs'); return b
            try:
                obs = one(k for k in ev if k.startswith('research/') and k.endswith('-observed.json'))
                r = json.loads(read(small,obs)); child = json.loads(read(big,one(k for k in ev if k.endswith('/client/observed.json'))))
                check(child == r['child'] and child['terminal_sha256']==exe['SHA256'] and child['client_sha256']==ident['clients'][client]['sha256'] and
                      r['client']==client and r['requested_renderer']==renderer and r['session']['renderer']=={'gdi':0,'directx':2}[renderer] and
                      r['global_input'] and r['font']==FONT, 'client, renderer, font or input mismatch')
                full = read(big,one(k for k in ev if k.endswith('-client-output.vt'))); first = read(big,one(k for k in ev if k.endswith('-at-drag.vt')))
                check(full.startswith(first) and digest(first)==r['bidi_system_copy']['wire_sha256'], 'first VT snapshot differs')
                stem = obs.removesuffix('observed.json'); member = lambda k: read(big,k)
                row['stages']['first'] = inspect_stage(member,r,r,stem+'bidi-',False,first)
                reply = r['bidi_roundtrip']; second = prefix_at_digest(full,len(first),reply['bidi_system_copy']['wire_sha256'])
                row['stages']['reply'] = s = inspect_stage(member,r,reply,stem+'reply-bidi-',True,second)
                expected = digest(('NEMOTERM_GLYPH_SUBMIT '+s['clipboard']).encode())
                submitted = one(v for v in child['requests'] if v['glyph_prompt_hashes'])
                check(reply['bitmap_sentinel'] and submitted==reply['receipt'] and submitted['glyph_prompt_hashes']==[expected] and
                      r['http_receipt']['selection_received'] and submitted['path']==r['http_receipt']['path'], 'exact pasted glyph missing from provider')
                row.update(verified=c['status']=='passed' and r['completed'] and not c['cleanup']['terminated_remaining'],
                           provider_path=submitted['path'],provider_prompt_sha256=expected)
            except (ValueError,KeyError,IndexError,OSError) as error:
                row['error'] = str(error)  # Keep failures and continue reading other original attempts.
    return dict(executable=exe,product=source['SourceCommit'],fixture=ident['fixture_commit'],cases=rows,
                stages_verified=sum(len(r['stages']) for r in rows.values()),verified=sum(r['verified'] for r in rows.values()),expected=len(wanted))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('receipt','surfaces','output'): parser.add_argument(arg,type=Path)
    args = parser.parse_args(); result = review(args.receipt,args.surfaces)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for name,r in result['cases'].items():
        if not r['verified']: print(name,r.get('error','original attempt incomplete'))
    print(f"Displayed RTL selection and provider: {result['verified']}/{result['expected']} windows, {result['stages_verified']} drags")
    raise SystemExit(0 if result['verified']==result['expected'] else 1)
