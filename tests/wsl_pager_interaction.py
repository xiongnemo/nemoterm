"""Observe real Linux less using both xterm terminfo entries in a hosted Nemoterm."""
import hashlib
import re
import shlex
import struct
import sys
from pathlib import Path

from native_test_utils import wait_for


def exercise(process, hwnd, folder, as_wsl, send, result, snapshots):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
    import nemoterm_debug as api
    instance = wait_for(lambda: next(iter(api.discover(process.pid)), None))
    session, = instance['sessions']
    sid = session['id']; endpoint = instance['endpoint']
    assert session['hwnd'] == hwnd, (session, hwnd)
    script = folder/'pager.sh'
    script.write_bytes(r"""set -eu
cd -- "$(dirname -- "$0")"
phase=$1
if [ "$phase" = plain ]; then export TERM=xterm; fi
unset LESS LESSKEY LESSKEYIN LESSOPEN LESSCLOSE LESSANSIENDCHARS LESSANSIMIDCHARS
export LESSHISTFILE=- LC_ALL=C
{ printf 'TERM=%s\n' "$TERM"; command -v less; less --version; } >"pager-$phase-id"
printf '\033[2J\033[HNEMOTERM_PRIOR_%s\n' "$phase"
IFS= read -r ack
less -+F -+X -- pager.txt
printf '%s' "$?" >"pager-$phase-exit"
""".encode('ascii'))
    (folder/'pager.txt').write_bytes(''.join(f'PAGERROW{i:04d} {"ZEBRA_NEEDLE" if i == 220 else "line"}\n' for i in range(1, 501)).encode('ascii'))
    def key(vk): api.request(endpoint, 'key', sid, struct.pack('<II', vk, 0))
    for phase, term in [('inherited','xterm-256color'), ('plain','xterm')]:
        evidence = result[phase] = dict(steps=[])
        prior = 'NEMOTERM_PRIOR_' + phase
        def observe(label, accept):
            def read():
                assert process.poll() is None, process.returncode
                screen = api.request(endpoint,'text',sid)
                evidence['last_screen'] = screen
                rows = [int(x) for x in re.findall(r'(?m)^PAGERROW(\d{4}) ', screen)]
                return (screen,rows) if accept(screen, rows) else None
            screen, rows = wait_for(read,timeout=15)
            name = f'wsl-less-{phase}-{label}.png'
            data = api.png_from_bmp(api.request(endpoint,'image',sid)); (snapshots/name).write_bytes(data)
            evidence['steps'].append(dict(stage=label,screen=screen,rows=rows,image=name,image_sha256=hashlib.sha256(data).hexdigest()))
            return rows
        send(hwnd, 'bash '+shlex.quote(as_wsl(script,'wsl-bash'))+' '+phase+'\r')
        observe('before',lambda text,rows: prior in text and not rows)
        evidence['program'] = (folder/f'pager-{phase}-id').read_text(encoding='utf-8')
        assert evidence['program'].splitlines()[0] == 'TERM='+term and 'less ' in evidence['program'],evidence
        key(13)
        initial = observe('open',lambda text,rows: len(rows)>3 and rows[0]==1 and prior not in text)
        key(0x28)
        observe('down',lambda text,rows: len(rows)>3 and rows[0]==2)
        key(0x22)
        observe('page',lambda text,rows: len(rows)>3 and rows[0]>=len(initial) and rows[-1]<220)
        api.request(endpoint,'input',sid,'/ZEBRA_NEEDLE');key(13)
        observe('search',lambda text,rows: 'PAGERROW0220 ZEBRA_NEEDLE' in text and (219 in rows or 221 in rows))
        api.request(endpoint,'input',sid,'q')
        observe('restored',lambda text,rows: prior in text and not rows)
        log = folder/f'pager-{phase}-exit'
        wait_for(lambda: log.exists() and log.read_text(encoding='ascii')=='0')
        evidence.pop('last_screen'); evidence['completed']=True
