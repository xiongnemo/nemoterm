"""Click Cancel and type into the live child without repairing focus in the test."""
import os
if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
    raise SystemExit('Requires a GitHub-hosted desktop')
import traceback
from native_test_utils import (c, w, u, root, Path, hashlib, json, sys, struct, time,
    subprocess, tempfile, wait_for, read_snapshot)
from hosted_gesture_input import DesktopInput, Input
from protocol_oracle_window import saved_profile
from owned_job import OwnedJob
sys.path.insert(0, str(root/'tools'))
import nemoterm_debug as api

u.GetDlgItem.argtypes, u.GetDlgItem.restype = [w.HWND, c.c_int], w.HWND
u.GetWindow.argtypes, u.GetWindow.restype = [w.HWND, w.UINT], w.HWND
u.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
u.IsWindowEnabled.argtypes = [w.HWND]
exe = Path(os.environ['NEMOTERM_TEST_EXE']).resolve(strict=True)
output = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), cases={})

def exercise(mode, row):
    tabs = mode != 'standalone'
    with tempfile.TemporaryDirectory() as tmp, saved_profile(dict(NemoTabs=int(tabs),
            WarnOnClose=1, NemoShell='custom', NemoShellCommand='cmd.exe /d /q', CloseOnExit=1)) as profile, OwnedJob() as job:
        report = Path(tmp)/'report.json'
        proc = job.spawn([str(exe), '--automation', '--profile', profile[1], '--cols', '64', '--rows', '16',
            '-e', sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(Path(tmp)/'control.json'), '120'],
            env=dict(os.environ, NEMOTERM_CONPTY='bundled'), creationflags=subprocess.CREATE_NO_WINDOW)
        wait_for(lambda: 'hex' in read_snapshot(report))
        instance = wait_for(lambda: next(iter(api.discover(proc.pid)), None)); ep = instance['endpoint']
        seat = instance['sessions'][0]; term, host = seat['hwnd'], seat['window']
        assert (host != term) == tabs
        def sessions(): return api.request(ep)['sessions']
        if tabs:
            api.request(ep, 'key', seat['id'], struct.pack('<II', ord('T'), 3))
            other = wait_for(lambda: next((s for s in sessions() if s['id'] != seat['id'] and s['active']), None))
            api.request(ep, 'key', other['id'], struct.pack('<II', 9, 2))
            wait_for(lambda: any(s['id']==seat['id'] and s['active'] for s in sessions()))
        ids = {s['id'] for s in sessions()}; desktop = DesktopInput(proc.pid, host, term, row); win = desktop.u
        def state():
            g = desktop.state()
            return dict(foreground=win.GetForegroundWindow(), active=g.active, focus=g.focus, host=host, term=term,
                        enabled=bool(u.IsWindowEnabled(host)), received=read_snapshot(report).get('hex'))
        def pair(key):
            inputs=(Input*2)()
            for event in inputs: event.kind=1;event.key.key=key
            inputs[1].key.flags=2
            assert win.SendInput(2,inputs,c.sizeof(Input))==2
        try:
            desktop.chord(ord('A')); wait_for(lambda: read_snapshot(report).get('hex')=='61'); row['before']=state()
            expected=b'a';row['dismissals']=[]
            target=host if mode=='tab-window' else term
            for how,key in [('cancel-button','B'),('escape','C')]:
                step=dict(method=how);row['dismissals'].append(step)
                assert u.PostMessageW(target,0x10,0,0)
                dlg=wait_for(desktop.owned_confirmation);step['during']=state();assert not step['during']['enabled']
                pair(ord('X'))  # A real key while the dialog owns input must never reach the child.
                if how=='cancel-button': desktop.click_confirmation_button(dlg,2,step.setdefault('click',{}))
                else: assert desktop.owned_confirmation()==dlg;pair(0x1b)
                try: wait_for(lambda: not u.IsWindow(dlg) and u.IsWindowEnabled(host))
                finally: step.update(popup_alive=bool(u.IsWindow(dlg)),dismissed_state=state())
                # Observe only. Never bring the app forward, select a tab or click its client here.
                step['after']=state()
                if win.GetForegroundWindow()==host: pair(ord(key))
                expected+=key.lower().encode()
                try: wait_for(lambda: read_snapshot(report).get('hex')==expected.hex(),timeout=3)
                finally: step['typed']=state()
                assert step['typed']['focus']==term and {s['id'] for s in sessions()}==ids
            assert u.PostMessageW(target,0x10,0,0);dlg=wait_for(desktop.owned_confirmation)
            confirm=row['confirm']={};desktop.click_confirmation_button(dlg,1,confirm)
            try: wait_for(lambda: not u.IsWindow(dlg))
            finally: confirm.update(popup_alive=bool(u.IsWindow(dlg)),host_alive=bool(u.IsWindow(host)),exit_code=proc.poll())
            if mode=='tab-session':
                wait_for(lambda: len(sessions())==1 and sessions()[0]['id']==other['id'])
            else: assert proc.wait(timeout=12)==0
            row['ok_closed']=True
        finally: desktop.restore()

for mode in ('tab-session','tab-window','standalone'):
    row=output['cases'][mode]={}
    try: exercise(mode,row);row['passed']=True
    except Exception: row.update(passed=False,error=traceback.format_exc())
    print(mode,row.get('error','passed'),flush=True)
    (root/'research'/'dialog-close-input.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
raise SystemExit(0 if all(row['passed'] for row in output['cases'].values()) else 1)
