"""Observe real Linux less using both xterm terminfo entries in a hosted Nemoterm."""
import hashlib
import re
import os
import traceback
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
phase=$1; branch=$2; transport=$3
if [ "$branch" = plain ]; then export TERM=xterm; fi
unset LESS LESSKEY LESSKEYIN LESSOPEN LESSCLOSE LESSANSIENDCHARS LESSANSIMIDCHARS
export LESSHISTFILE=- LC_ALL=C
{ printf 'TERM=%s\n' "$TERM"; command -v less; less --version; for cap in kcuu1 kcud1 knp smkx rmkx; do printf '%s=' "$cap"; tput "$cap" | od -An -tx1 | tr -d ' \n'; printf '\n'; done; } >"pager-$phase-id"
printf '\033[2J\033[HNEMOTERM_PRIOR_%s\n' "$phase"
IFS= read -r ack
if [ "$transport" = direct ]; then
  less -+F -+X -- pager.txt
else
  script -qef --log-in "pager-$phase-input" --log-out "pager-$phase-output" -c 'exec less -+F -+X -- pager.txt'
fi
printf '%s' "$?" >"pager-$phase-exit"
""".encode('ascii'))
    (folder/'pager.txt').write_bytes(''.join(f'PAGERROW{i:04d} {"ZEBRA_NEEDLE" if i == 220 else "line"}\n' for i in range(1, 501)).encode('ascii'))
    def api_key(vk): api.request(endpoint, 'key', sid, struct.pack('<II', vk, 0))
    diagnostics = os.environ.get('NEMOTERM_WSL_KEY_DIAGNOSTICS') == '1'
    trials = [('inherited','xterm-256color','direct','api'), ('plain','xterm','direct','api')]
    if diagnostics:
        base = list(trials)
        trials += [(phase+'-system-direct',term,'direct','system') for phase,term,_,_ in base]
        trials += [(phase+'-'+method+'-recorded',term,'recorded',method)
                   for phase,term,_,_ in base for method in ('api','system')]
    failures=[]
    for phase, term, transport, method in trials:
        evidence = result[phase] = dict(steps=[], transport=transport, method=method)
        desktop = None
        prior = 'NEMOTERM_PRIOR_' + phase
        def key(vk):
            if desktop is None: return api_key(vk)
            if vk in (0x28,0x22):
                # Both the down and up events originate from the dedicated
                # arrow/navigation cluster, not the numeric keypad.
                desktop.event(vk,True,extended=True);desktop.event(vk,False,extended=True)
            else: desktop.chord(vk)
        def observe(label, accept):
            evidence['current_stage']=label
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
        log = folder/f'pager-{phase}-exit'
        try:
            if method=='system':
                from hosted_gesture_input import DesktopInput
                desktop=DesktopInput(process.pid,session['window'],hwnd,evidence.setdefault('desktop',{}))
            args = [as_wsl(script,'wsl-bash'), phase, 'plain' if term=='xterm' else 'inherited', transport]
            send(hwnd, 'bash '+shlex.join(args)+'\r')
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
            wait_for(lambda: log.exists() and log.read_text(encoding='ascii')=='0')
            if transport=='recorded':
                # script(1) writes one header and footer around the unmodified PTY bytes.
                evidence['current_stage']='input-bytes'
                raw=(folder/f'pager-{phase}-input').read_bytes()
                header,_,tail=raw.partition(b'\n'); payload,footer,end=tail.rpartition(b'\nScript done on ')
                caps=dict(line.split('=',1) for line in evidence['program'].splitlines() if '=' in line)
                expected=bytes.fromhex(caps['kcud1']+caps['knp'])+b'/ZEBRA_NEEDLE\rq'
                evidence['input_bytes']=dict(expected=expected.hex(),observed=payload.hex())
                assert header.startswith(b'Script started on ') and footer and b'COMMAND_EXIT_CODE="0"' in end
                assert payload==expected,evidence['input_bytes']
            evidence.pop('last_screen'); evidence['completed']=True
        except Exception:
            failed_stage=evidence['current_stage'] if 'current_stage' in evidence else 'launch'
            failures.append((phase,failed_stage));evidence.update(completed=False,failed_stage=failed_stage,error=traceback.format_exc(),failure_screen=evidence.get('last_screen'))
            if failed_stage!='launch':
                (snapshots/f'wsl-less-{phase}-failed-{failed_stage}.png').write_bytes(api.png_from_bmp(api.request(endpoint,'image',sid)))
            if failed_stage=='down':
                # A separate printable navigation control does not satisfy the arrow gate.
                api.request(endpoint,'input',sid,'j')
                try: observe('diagnostic-letter-j',lambda text,rows: len(rows)>3 and rows[0]==2)
                except Exception:evidence['letter_error']=traceback.format_exc()
        finally:
            if desktop:desktop.restore()
            if evidence.get('completed') is not True and not log.exists():
                api.request(endpoint,'input',sid,'q')
                try:wait_for(log.exists,timeout=4)
                except Exception:evidence['quit_error']=traceback.format_exc()
            for direction in ('input','output'):
                source=folder/f'pager-{phase}-{direction}'
                if source.is_file():
                    raw=source.read_bytes();(snapshots/f'wsl-less-{phase}-{direction}.vt').write_bytes(raw)
                    evidence[direction+'_sha256']=hashlib.sha256(raw).hexdigest()
            if not log.exists():break  # Child state is unknown; never type another command into it.
    if failures:raise AssertionError(('less interactions',failures))
