"""Click Cancel and type into the live child without repairing focus in the test."""
import os
if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
    raise SystemExit('Requires a GitHub-hosted desktop')
import traceback
from native_test_utils import (c, w, u, root, Path, hashlib, json, sys, struct, time,
    subprocess, tempfile, wait_for, read_snapshot)
from fixture_io import write_snapshot
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

def dialog_words(dlg):
    # Read window-owned Unicode strings from the runner's live dialog. WM_GETTEXT
    # is marshalled by USER32; no access to the terminal process memory is needed.
    send=u.SendMessageTimeoutW
    send.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM,w.UINT,w.UINT,c.POINTER(c.c_size_t)]
    def read(hwnd):
        buf=c.create_unicode_buffer(1024); count=c.c_size_t()
        assert send(hwnd,0x000d,len(buf),c.addressof(buf),2,1000,c.byref(count)) and count.value<len(buf)-1
        return buf.value
    controls=[]
    @c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
    def visit(hwnd,_):
        kind=c.create_unicode_buffer(64);u.GetClassNameW(hwnd,kind,len(kind))
        if kind.value=='Static' and u.IsWindowVisible(hwnd):controls.append(hwnd)
        return True
    u.EnumChildWindows(dlg,visit,0)
    return dict(title=read(dlg),body=[text for hwnd in controls if (text:=read(hwnd))])


def exercise(mode, language, row):
    tabs = mode != 'standalone'
    with tempfile.TemporaryDirectory() as tmp, saved_profile(dict(NemoTabs=int(tabs),
            WarnOnClose=1, NemoTabSide=0, NemoShell='custom', NemoShellCommand='cmd.exe /d /q', CloseOnExit=1)) as profile, OwnedJob() as job:
        report,control = Path(tmp)/'report.json',Path(tmp)/'control.json'
        proc = job.spawn([str(exe), '--automation', '--ui-language', language, '--profile', profile[1], '--cols', '64', '--rows', '16',
            '-e', sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control), '120'],
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
            def request_close():
                if mode!='background-tab':
                    assert u.PostMessageW(target,0x10,0,0);return
                # A middle click on the second (inactive) label must not switch seats.
                r=w.RECT();assert u.GetClientRect(host,c.byref(r));dpi=u.GetDpiForWindow(host)
                height=(28*dpi+48)//96; extent=min((168*dpi+48)//96,(r.right-height)//2)
                pt=w.POINT(extent+extent//3,height//2);assert u.ClientToScreen(host,c.byref(pt))
                desktop.move_screen(pt.x,pt.y)
                def arrived():
                    cursor=w.POINT();return (win.GetCursorPos(c.byref(cursor)) and (cursor.x,cursor.y)==(pt.x,pt.y)
                                              and win.WindowFromPoint(cursor)==host)
                wait_for(arrived);desktop.event('middle',True);desktop.event('middle',False)
            for how,key in [('cancel-button','B'),('escape','C')]:
                step=dict(method=how);row['dismissals'].append(step)
                request_close()
                dlg=wait_for(desktop.owned_confirmation);step['words']=dialog_words(dlg);step['during']=state();assert not step['during']['enabled']
                pair(ord('X'))  # A real key while the dialog owns input must never reach the child.
                # Trigger normal VT output from the already running child
                # while the system dialog owns the foreground. Observe its
                # acknowledgement without asking the modal GUI thread to work.
                marker=f'NEMO_REPLY_{proc.pid}_{key}'
                write_snapshot(control,dict(report_responses=True,responses={marker:{
                    'trigger':'61','sequence':'\r\n'+marker+'\r\n'}}))
                flushed=wait_for(lambda: snap if marker in (snap:=read_snapshot(report)).get('flushed_responses',[]) else None)
                step['background_output']=dict(marker=marker,flushed=True,during=state())
                assert (flushed['hex']==expected.hex() and desktop.owned_confirmation()==dlg
                        and not step['background_output']['during']['enabled']),step
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
                screen=wait_for(lambda: text if marker in (text:=api.request(ep,'text',seat['id'])) else None)
                assert screen.count(marker)==1,(marker,screen)
                step['background_output'].update(visible_after_key=True,matched_line=next(line.strip()
                    for line in screen.splitlines() if marker in line))
            request_close();dlg=wait_for(desktop.owned_confirmation)
            confirm=row['confirm']={};desktop.click_confirmation_button(dlg,1,confirm)
            try: wait_for(lambda: not u.IsWindow(dlg))
            finally: confirm.update(popup_alive=bool(u.IsWindow(dlg)),host_alive=bool(u.IsWindow(host)),exit_code=proc.poll())
            if mode in ('tab-session','background-tab'):
                remaining_id=other['id'] if mode=='tab-session' else seat['id']
                wait_for(lambda: [s['id'] for s in sessions() if s['active']]==[remaining_id] and len(sessions())==1)
                if mode=='background-tab':
                    pair(ord('D'));wait_for(lambda: read_snapshot(report).get('hex')=='61626364')
                    assert state()['focus']==term
                assert u.PostMessageW(host,0x10,0,0);dlg=wait_for(desktop.owned_confirmation)
                desktop.click_confirmation_button(dlg,1,row.setdefault('last_window_close',{}));assert proc.wait(timeout=12)==0
            else: assert proc.wait(timeout=12)==0
            row['ok_closed']=True
            window=mode=='tab-window';zh=language=='zh-CN'
            body=(('关闭此窗口及其中的所有终端标签页？' if zh else 'Close this window and all its terminal tabs?') if window else
                  ('确定要关闭此会话吗？' if zh else 'Are you sure you want to close this session?'))
            title='Nemoterm' if window else ('Nemoterm 退出确认' if zh else 'Nemoterm Exit Confirmation')
            row['expected_dialog']=dict(title=title,body=body)
            assert all(v['words']['title']==title and body in v['words']['body'] for v in row['dismissals']), row['expected_dialog']
        finally: desktop.restore()

for language in ('en','zh-CN'):
    for mode in ('tab-session','tab-window','standalone','background-tab'):
        row=output['cases'][mode if language=='en' else language+'-'+mode]=dict(language=language)
        try: exercise(mode,language,row);row['passed']=True
        except Exception: row.update(passed=False,error=traceback.format_exc())
        print(language,mode,row.get('error','passed'),flush=True)
        (root/'research'/'dialog-close-input.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
raise SystemExit(0 if all(row['passed'] for row in output['cases'].values()) else 1)
