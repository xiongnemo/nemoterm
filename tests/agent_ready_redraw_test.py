"""Remote regression for a real split prompt redraw and neighboring false positives."""
import hashlib
import io
from pathlib import Path
from zipfile import ZipFile
from agent_ready_redraw import IDLE, read_idle_redraw


def main():
    root = Path(__file__).resolve().parents[1]
    with ZipFile(root/'testdata/upstream/codex-file-clipboard-d457d34.zip') as pack:
        data = pack.read('14499253304.zip')
    assert hashlib.sha256(data).hexdigest() == '382643290f21a8b4e90bb10bce285ca67c1e17202e471ffd9398a0b4a2a5e1b1'
    with ZipFile(io.BytesIO(data)) as z:
        log, = [n for n in z.namelist() if n.endswith('/ctrl-v/client-output.log')]
        wire = z.read(log)
        screen = z.read(log.replace('client-output.log','failure.txt')).decode('utf-8')
    marker = 'NEMOTERM_CODEX_IMAGE_CTRL_V'
    get = lambda w=wire,s=screen:read_idle_redraw(w,marker,lambda:s)
    proof = get()
    assert (proof['kind'],proof['row'],proof['suffix_column']) == ('split-redraw',27,11), proof
    off = proof['suffix_write']; pre,post = wire[:off],wire[off:]
    assert post.startswith(b'\x1b[27;11H')
    assert not get(pre+post.replace(b'27;11H',b'27;12H',1))  # correct text, wrong column
    assert not get(pre+post.replace(b'27;11H',b'26;11H',1))  # wrong row
    assert not get(pre+post.replace(b'_CODEX_IMAGE_CTRL_V',b'_CODEX_IMAGE_CTRL_C',1))
    assert not get(wire.replace(b'NEMOTERM\x1b',b'NEMOTERX\x1b'))
    assert not get(wire.replace(IDLE,b'\x1b]7501;state=working:app=codex'))
    assert not get(wire.replace(b'\x1b]10;?',b''))
    assert not get(s=screen.replace(marker,marker[:-1]))  # do not trust wire alone
    assert not get(wire[:wire.index(IDLE)])
    assert not get(wire[:wire.index(IDLE)] + marker.encode() + IDLE + b'\x1b\\')
    assert get(wire + marker.encode())['kind'] == 'complete-write'
    print('Recorded split repaint, full redraw, stale and mismatched controls passed.')


if __name__ == '__main__':
    main()
