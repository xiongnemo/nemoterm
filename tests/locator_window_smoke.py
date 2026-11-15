"""DEC Locator through genuine pointer input on a disposable Windows CI desktop.

Queries and events traverse the actual Win32 frontend and bundled ConPTY. The
literal cell replies match the retained XTerm capture; pixel replies use the
measured native viewport. This fixture intentionally does not run locally.
"""
from native_test_utils import (root, c, w, u, hashlib, json, os, subprocess,
    sys, tempfile, Path, time, read_snapshot, write_snapshot, wait_for, find_window,
    terminal_host, capture)
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile

assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Requires disposable CI desktop'
u.GetCursorPos.argtypes = [c.POINTER(w.POINT)]
u.ClientToScreen.argtypes = [w.HWND, c.POINTER(w.POINT)]
u.GetClientRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.SetCursorPos.argtypes = [c.c_int, c.c_int]
u.SetForegroundWindow.argtypes = [w.HWND]
u.mouse_event.argtypes = [w.DWORD, w.DWORD, w.DWORD, w.DWORD, c.c_size_t]
u.GetAsyncKeyState.argtypes = [c.c_int]
u.GetAsyncKeyState.restype = c.c_short
exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
evidence = dict(completed=False, executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                reference='XTerm(412) DEC Locator; native coordinates measured independently',
                checks={}, physical_input=True)
CSI = '\x1b['
marker = b'\x1b[0n'
saved = w.POINT()
assert u.GetCursorPos(c.byref(saved))
held = set()
shift_held = False
button_info = {1:(0x02,0x04,0,0x01), 2:(0x20,0x40,0,0x04),
               3:(0x08,0x10,0,0x02), 4:(0x80,0x100,1,0x05)}

with saved_profile(dict(NoMouseReporting=0, WarnOnClose=0, NemoRenderer=0)) as profile, \
        tempfile.TemporaryDirectory(prefix='nemoterm-locator-') as directory, OwnedJob() as job:
    folder = Path(directory)
    report, control = folder/'report.json', folder/'control.json'
    process = job.spawn([str(exe), *profile, '--cols', '80', '--rows', '24', '-e',
        sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control), '180'],
        env=dict(os.environ, NEMOTERM_CONPTY='bundled', NEMOTERM_TEST_EXACT_OUTPUT='1'),
        creationflags=subprocess.CREATE_NO_WINDOW)

    def current():
        value = read_snapshot(report)
        assert not value.get('error') and process.poll() is None, value
        return value

    def phase(name, sequence, reply=b''):
        request = dict(phase=name, sequence=sequence+CSI+'5n', preserve_mouse=True)
        write_snapshot(control, request)
        expected = reply+marker
        value = wait_for(lambda: (d := current()).get('phase') == name and
                         bytes.fromhex(d.get('hex','')).endswith(marker) and d)
        assert bytes.fromhex(value['hex']) == expected, (name, value, expected)
        evidence['checks'][name] = dict(sequence_hex=sequence.encode().hex(), reply_hex=reply.hex())
        return request, expected

    def events(request, prefix, action, expected):
        action()
        if expected:
            wait_for(lambda: bytes.fromhex(current().get('hex','')) == prefix+expected)
        else:
            time.sleep(.15)
        request['input_barrier'] = request['phase']+'-input'
        write_snapshot(control, request)
        value = wait_for(lambda: (d := current()).get('input_barrier') == request['input_barrier'] and d)
        assert bytes.fromhex(value['hex']) == prefix+expected+marker, (request['phase'], value, expected)
        evidence['checks'][request['phase']]['event_reply_hex'] = expected.hex()

    def geometry():
        d = current(); rect = w.RECT()
        assert u.GetClientRect(hwnd, c.byref(rect))
        cols, rows = d['columns'], d['rows']
        cw, ch = (rect.right-2)//cols, (rect.bottom-2)//rows
        ox, oy = (rect.right-cols*cw)//2, (rect.bottom-rows*ch)//2
        assert cw > 0 and ch > 0 and 0 <= ox <= cw and 0 <= oy <= ch
        return cols, rows, cw, ch, ox, oy

    def position(col, row):
        _, _, cw, ch, ox, oy = geometry()
        point = w.POINT(ox+(col-1)*cw+cw//2, oy+(row-1)*ch+ch//2)
        client = [point.x, point.y]
        assert u.ClientToScreen(hwnd, c.byref(point)) and u.SetCursorPos(point.x, point.y)
        time.sleep(.08)
        return client

    def button(number, down):
        press, release, data, vk = button_info[number]
        u.mouse_event(press if down else release, 0, 0, data, 0)
        if down: held.add(number)
        else: held.discard(number)
        wait_for(lambda: bool(u.GetAsyncKeyState(vk) & 0x8000) == down)
        time.sleep(.06)

    try:
        hwnd = wait_for(lambda: find_window(process.pid))
        wait_for(lambda: current().get('columns') == 80 and current().get('rows') == 24)
        assert u.SetForegroundWindow(terminal_host(hwnd))
        for _, _, _, vk in button_info.values(): assert not u.GetAsyncKeyState(vk) & 0x8000
        phase('status', CSI+'65;1"p'+CSI+'?25l'+CSI+'?55n'+CSI+'?56n', b'\x1b[?50n\x1b[?57;1n')
        _,_,cw,ch,_,_ = geometry()
        phase('cell-geometry', CSI+'16t', f'\x1b[6;{ch};{cw}t'.encode())
        position(12, 7)
        phase('disabled', CSI+"'|", b'\x1b[0&w')
        phase('live-query', CSI+"1;2'z"+CSI+"'|", b'\x1b[1;0;7;12&w')
        point = position(15, 9)
        phase('moved-query', CSI+"'|", b'\x1b[1;0;9;15&w')
        phase('pixel-query', CSI+"1;1'z"+CSI+"'|", f'\x1b[1;0;{point[1]+1};{point[0]+1}&w'.encode())
        position(12, 7)
        for number, mask in ((1,4),(2,2),(3,1),(4,8)):
            request, prefix = phase(f'button-{number}-down', CSI+"1;2'z"+CSI+"1;3'{")
            events(request, prefix, lambda: button(number, True), f'\x1b[{2*number};{mask};7;12&w'.encode())
            phase(f'held-{number}', CSI+"'|", f'\x1b[1;{mask};7;12&w'.encode())
            request, prefix = phase(f'button-{number}-up', '')
            events(request, prefix, lambda: button(number, False), f'\x1b[{2*number+1};0;7;12&w'.encode())
        phase('once', CSI+"2'z"+CSI+"'|"+CSI+"'|", b'\x1b[1;0;7;12&w\x1b[0&w')
        request, prefix = phase('filter-leave', CSI+"1;2'z"+CSI+"5;10;9;15'w")
        events(request, prefix, lambda: position(16,10), b'\x1b[10;0;10;16&w')
        phase('filter-retains-continuous', CSI+"'|", b'\x1b[1;0;10;16&w')
        phase('query-cancels-filter', CSI+"'w"+CSI+"'|", b'\x1b[0&w')
        position(12, 7)
        request, prefix = phase('shift-local', CSI+'7;1HABCDEFGHIJKLMNOPQRSTUVWXYZ'+CSI+"1;2'z"+CSI+"1;3'{")
        before_selection = capture(hwnd, return_pixels=True)
        def local_selection():
            global shift_held
            assert not u.GetAsyncKeyState(0x10) & 0x8000
            u.keybd_event(0x10,0x2a,0,0); shift_held = True
            wait_for(lambda: u.GetAsyncKeyState(0x10) & 0x8000)
            button(1, True); position(18,7); button(1, False)
            u.keybd_event(0x10,0x2a,2,0); shift_held = False
        events(request, prefix, local_selection, b'')
        selected = wait_for(lambda: (pixels := capture(hwnd, return_pixels=True)) != before_selection and pixels)
        evidence['shift_selection_pixels'] = dict(before_sha256=hashlib.sha256(before_selection).hexdigest(),
                                                  after_sha256=hashlib.sha256(selected).hexdigest())
        # Query reads the current pointer even though Shift input was local.
        phase('query-after-local-selection', CSI+"'|", b'\x1b[1;0;7;18&w')
        old = geometry()[:2]
        assert u.MoveWindow(terminal_host(hwnd),80,80,700,500,True)
        wait_for(lambda: (current().get('columns'),current().get('rows')) != old)
        cols,rows,_,_,_,_ = geometry()
        position(cols,rows)
        phase('resized-query', CSI+"'|", f'\x1b[1;0;{rows};{cols}&w'.encode())
        evidence['resized_grid'] = [cols,rows]
        assert u.SetCursorPos(0,0)
        phase('outside-query', CSI+"'|", b'\x1b[0&w')
        phase('reset-disables', '\x1bc'+CSI+"'|", b'\x1b[0&w')
        write_snapshot(control, dict(stop=True))
        process.wait(timeout=10)
        assert process.returncode == 0
        evidence['cleanup'] = job.finish()
        assert not evidence['cleanup']['terminated_remaining']
        evidence['completed'] = True
        print('Native Locator:', len(evidence['checks']), 'phases passed')
    finally:
        evidence['last_snapshot'] = read_snapshot(report)
        for number in list(held):
            _, release, data, _ = button_info[number]
            u.mouse_event(release,0,0,data,0)
        if shift_held: u.keybd_event(0x10,0x2a,2,0)
        u.SetCursorPos(saved.x,saved.y)
        evidence.setdefault('cleanup',job.finish(grace=0))
        (root/'research/locator-window-observed.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
