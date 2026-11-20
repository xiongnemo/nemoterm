"""Compare the OS cwd of freshly opened tabs with the OSC 7 directory on the original tab."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback

from clipboard_test_utils import SavedClipboard, clipboard_text
from fixture_io import read_snapshot, write_snapshot, wait_snapshot
from hosted_gesture_input import DesktopInput
from native_test_utils import c, w, u, root, find_window, terminal_host, wait_for
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile


def exercise(exe, renderer, rec):
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp); initial = base/'start'; target = base/'chosen 中;#%'; seed = base/'previous'
        for d in (initial, target, seed): d.mkdir()
        command = subprocess.list2cmdline([sys.executable, str(root/'tests/session_fixture.py'), tmp, '180', '--unique-mailbox'])
        env = dict(os.environ, NEMOTERM_CONPTY='bundled', NEMOTERM_TEST_EXACT_OUTPUT='1')
        profile = dict(NemoShell='custom', NemoShellCommand=command, NemoTabs=1, NemoRenderer=renderer-1,
                       NemoInheritDirectory=1, WarnOnClose=0, CloseOnExit=1, Font=os.environ['NEMOTERM_TEST_FONT'])
        with saved_profile(profile) as flags, OwnedJob() as job:
            proc = job.spawn([str(exe), *flags, '--tabs', '--directory', str(initial)], env=env,
                             creationflags=subprocess.CREATE_NO_WINDOW)
            seen = set(); desk = clip = None
            def next_child():
                def fresh():
                    for f in base.glob('*.launch.json'):
                        if f.name not in seen and (r := read_snapshot(f)) and r['parent'] == proc.pid:
                            seen.add(f.name); return r
                return wait_for(fresh, timeout=15)
            def channel(child, kind): return base/(child['mailbox']+'.'+kind+'.json')
            def emit(seq, label):
                write_snapshot(channel(first,'control'), dict(phase=label, preserve_mouse=True, sequence=seq+'\x1b[5n'))
                return wait_snapshot(lambda: read_snapshot(channel(first,'report')),
                                     lambda r: r.get('phase')==label and r.get('hex','').endswith('1b5b306e'))['hex']
            try:
                first = next_child(); rec['original'] = first; assert Path(first['cwd']) == initial
                hwnd = wait_for(lambda:find_window(proc.pid)); host = terminal_host(hwnd); assert host != hwnd
                u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND,w.LPCWSTR], w.HANDLE
                rec['renderer'] = u.GetPropW(hwnd,'NemotermRenderer'); assert rec['renderer']==renderer
                desk = DesktopInput(proc.pid,host,hwnd,rec.setdefault('keys',{})); clip = SavedClipboard(hwnd)
                canonical = target.as_uri(); path = canonical.removeprefix('file://'); assert path.startswith('/')
                remote = 'file://remote.invalid'+path
                cases = [('standard', canonical, canonical, target), ('one-slash', 'file:'+path, canonical, target),
                         ('mixed-case', 'FiLe://'+path, canonical, target), ('upper-one-slash', 'FILE:'+path, canonical, target),
                         ('remote', remote, remote, initial), ('relative', 'file:child', seed.as_uri(), seed),
                         ('bad-percent', 'file:'+path+'%00', seed.as_uri(), seed)]
                for i,(name, incoming, expected_uri, expected_dir) in enumerate(cases):
                    row = dict(name=name, sent=incoming, expected_uri=expected_uri, expected_dir=str(expected_dir));rec['cases'].append(row)
                    # A rejected input should leave the previous report intact. Never let one passing row seed the next.
                    row['fence_hex'] = emit('\x1b]7;'+seed.as_uri()+'\a\x1b]7;'+incoming+'\x1b\\', 'osc7-'+str(i))
                    u.SendMessageW(hwnd,0x111,0x1e0,0); row['copied_uri'] = clipboard_text(hwnd)
                    desk.chord(0x11,0x10,ord('T')); new = next_child(); row['launch'] = new
                    second = wait_for(lambda:h if (h:=find_window(proc.pid)) and h!=hwnd else None)
                    assert terminal_host(second)==host and new['mailbox']!=first['mailbox']
                    row['matches'] = Path(new['cwd'])==expected_dir and row['copied_uri']==expected_uri
                    write_snapshot(channel(new,'control'),{'stop':True});wait_for(lambda:not u.IsWindow(second) and find_window(proc.pid)==hwnd)
                clip.restore();clip=None;desk.restore();desk=None
                write_snapshot(channel(first,'control'),{'stop':True}); rec['exit_code']=proc.wait(timeout=12)
                rec['cleanup']=job.finish();assert rec['exit_code']==0 and not rec['cleanup']['terminated_remaining']
            finally:
                if desk: desk.restore()
                if clip: clip.restore()


if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    exe = Path(os.environ['NEMOTERM_TEST_EXE']); report=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),font=os.environ['NEMOTERM_TEST_FONT'],windows=[])
    for renderer in (1,3):
        rec=dict(requested=renderer,cases=[]);report['windows'].append(rec)
        try: exercise(exe, renderer, rec)
        except Exception: rec['error']=traceback.format_exc();print(rec['error'])
    (root/'research/osc7-tab-directory.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    assert all(not r.get('error') and len(r['cases'])==7 and all(x['matches'] for x in r['cases']) for r in report['windows']), 'See OSC 7 URI and actual child cwd for each tab'
