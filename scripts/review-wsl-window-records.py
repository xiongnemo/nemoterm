"""Read saved Windows runner receipts and screenshots for Sixel, Vim, and tmux/Vim."""
import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageChops


FONT = 'SarasaTermSC Nerd Light'
BUFFER = ['VIM_MOUSE_HEAD', 'COPY 中文 tail', 'CLICK_CURSOR_TARGET', 'UNCHANGED_END']
SAVED = [*BUFFER[:2], BUFFER[2] + '中文', BUFFER[3]]


def image(data):
    return Image.open(BytesIO(data)).convert('RGB')


def selection(before, after, cw, ch, row, columns):
    assert before.size == after.size
    for col in range(4, 10):
        box = (1 + col*cw, 1 + row*ch, 1 + (col+1)*cw, 1 + (row+1)*ch)
        diff = ImageChops.difference(before.crop(box), after.crop(box)).convert('L')
        changed = 1 - diff.histogram()[0] / (cw*ch)
        assert (changed > .5 if col in columns else changed < .1), (box, changed)


def editor(z, prefix, sha, mode):
    def data(name):
        return z.read(prefix + name)

    r = json.loads(data('result.json'))
    assert r['sha256'] == sha and r['font'] == FONT and r['completed'] and not r.get('forced_cleanup')
    assert r['rectangle_copied'] == '中文\r\nCU' and data('buffer.txt') == ('\n'.join(SAVED)+'\n').encode()
    assert data('vim-exit').strip() == b'0' and data('insert-events').splitlines()[-2:] == [b'enter', b'leave']
    dims = [(72, 24), (52, 16)]
    assert data('resizes').splitlines()[-2:] == [f'{w}x{h}'.encode() for w,h in dims]
    states = {}
    for entry in r['states']:
        original = json.loads(data(f"state-{entry['request_id']}.json"))
        assert original == {k:v for k,v in entry.items() if k != 'stage'}
        assert original['term'] == (r['term'] if mode == 'vim' else 'tmux-256color')
        states[entry['stage']] = original
    start = states['initial']
    assert start['grid'] == [60,20] and start['mouse'] == 'a' and start['ttymouse'] == 'sgr'
    for stage, grid in [('normal-click', [60,20]), ('shift-copy', [60,20]), ('72x24', [72,24]), ('52x16', [52,16])]:
        st = states[stage]
        assert st['cursor'] == [3,5] and st['lines'] == BUFFER and st['mode'] == 'n' and st['grid'] == grid
    pre, post = states['before-rectangle'], states['rectangle-copied']
    assert pre['cursor'] == post['cursor'] and pre['lines'] == post['lines'] == SAVED
    if mode == 'tmux-vim':
        assert {c['stage'] for c in r['tmux_states']} >= {'initial','shift-copy','72x24','52x16','rectangle-copied'}
        for client in r['tmux_states']:
            w,h = states[client['stage']]['grid']
            assert client['exit'] == 0 and client['lines'] == [f"{r['term']}|{w}|{h}", f'{w}|{h}|0', 'on']
    sess = r['session']; cw, remw = divmod(sess['client_width']-2, 60); ch, remh = divmod(sess['client_height']-2, 20)
    assert remw == remh == 0 and sess['renderer'] == r['renderer']
    for w,h in dims:
        assert image(data(f'resize-{w}x{h}.png')).size == (2+w*cw, 2+h*ch)
    selection(image(data('before-drag.png')), image(data('selection.png')), cw, ch, 1, range(5,9))
    before, after = image(data('before-rectangle.png')), image(data('rectangle.png'))
    selection(before, after, cw, ch, 1, range(5,9)); selection(before, after, cw, ch, 2, range(6,8))
    return (r['renderer'], r['term'])


def sixel(z, prefix, sha, name, renderer):
    r = json.loads(z.read(prefix+'result.json'))
    assert r['executable_sha256'] == sha and r['completed'] and r['requested'] == name and r['font'] == FONT
    assert r['session']['renderer'] == renderer and z.read(prefix+'producer.exit').strip() == b'0'
    def verified(stem):
        filename = stem + '.png'; data = z.read(prefix+filename)
        assert sha256(data).hexdigest() == r['file_hashes'][filename], filename
        return image(data)
    dec = verified('decoded'); assert dec.size == (24,18) and len(dec.getcolors()) == 5
    assert dec.tobytes() == verified('source-rgb').tobytes()
    blank = Image.new('RGB',(26,20)); painted = blank.copy(); painted.paste(dec,(1,1))
    assert painted.tobytes() == verified('guarded-reference').tobytes()
    for stage, ref in [('before',blank), ('drawn',painted), ('repainted',painted), ('erased',blank)]:
        sample = verified(stage).crop(r['guarded_crop'])
        assert sample.size == ref.size and sample.tobytes() == ref.tobytes(), (name,stage)


def review(vim, tmux, graphic):
    identity = None; records = {}
    for kind,path in [('vim',vim), ('tmux-vim',tmux), ('sixel',graphic)]:
        with ZipFile(path) as z:
            m = json.loads(z.read('wsl-product/SOURCE-HOST.json'))
            if identity is None: identity = m
            assert m == identity; sha = m['Executable']['SHA256']
            if kind == 'sixel':
                for name,number in [('gdi',0), ('directx',2)]:
                    sixel(z, f'wsl-check/research/wsl-sixel-{name}/', sha, name, number)
                records[kind] = {'renderers': ['gdi','directx'], 'verified_frames': 8}
            else:
                prefix = 'wsl-check/research/wsl-' + kind + '-'
                cases = [editor(z,n[:-len('result.json')],sha,kind) for n in z.namelist() if n.startswith(prefix) and n.endswith('/result.json')]
                assert sorted(cases) == [(r,t) for r in (0,2) for t in ('xterm','xterm-256color')]
                records[kind] = {'windows': sorted(cases), 'copied_rectangle': '中文\r\nCU'}
            records[kind]['archive_sha256'] = sha256(path.read_bytes()).hexdigest()
    return dict(product=identity['SourceCommit'], exe=identity['Executable']['SHA256'], records=records)


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    for arg in ('vim','tmux','sixel'): cli.add_argument(arg, type=Path)
    args=cli.parse_args();print(json.dumps(review(args.vim,args.tmux,args.sixel),indent=2))
