"""Exercise kitty negotiation and Win32 input through our own HWND and ConPTY.

No global keyboard/mouse injection, focus stealing, or layout activation.
"""
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, time, read_snapshot, write_snapshot, wait_snapshot,
    memory_sample, wait_for, find_window, capture)
from clipboard_test_utils import SavedClipboard, clipboard_text

with tempfile.TemporaryDirectory(prefix='nemoterm-keyboard-') as directory:
    directory = Path(directory)
    report, control = directory/'report.json', directory/'control.json'
    process = subprocess.Popen([str(root/'dist/nemoterm.exe'), '--cols', '80', '--rows', '24',
        '-e', sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control)],
        env=dict(os.environ, NEMOTERM_CONPTY='bundled'), creationflags=subprocess.CREATE_NO_WINDOW)
    handle = k.OpenProcess(0x410, False, process.pid)
    evidence, samples, saved = {}, [], None
    expected, phase_name = b'', ''

    def current():
        value = read_snapshot(report)
        assert not value.get('error') and process.poll() is None, value
        return value

    def check():
        try:
            value = wait_snapshot(current, lambda v: v.get('phase') == phase_name and
                                  bytes.fromhex(v.get('hex', '')) == expected)
            time.sleep(.06)  # Assert absence of late releases/duplicate text as well.
            value = wait_snapshot(current, lambda v: v.get('phase') == phase_name)
            assert bytes.fromhex(value['hex']) == expected, (phase_name, value, expected.hex())
        except AssertionError:
            raise AssertionError((phase_name, expected.hex(), current()))
        evidence[phase_name] = value
        samples.append(memory_sample(handle))

    def phase(name, sequence, reply):
        global phase_name, expected
        phase_name, expected = name, reply
        write_snapshot(control, {'phase':name, 'sequence':sequence})
        check()

    def key(vk, scan, event=1, count=1, system=False):
        lp = count | ((scan & 255) << 16) | ((scan & 256) << 16)
        if event != 1: lp |= 0x40000000
        if event == 3: lp |= 0x80000000
        if system: lp |= 0x20000000
        u.SendMessageW(hwnd, (0x104 if system else 0x100)+(event == 3), vk, lp)

    def tap(vk, scan):
        key(vk, scan); key(vk, scan, 3)

    def code(number, mods=0, event=1, text='', alternates='', final='u'):
        fields = mods or event != 1 or text
        number = str(number) if number != 1 or final == 'u' or fields else ''
        return ('\x1b['+number+alternates+(f';{mods+1}'+(f':{event}' if event != 1 else '')
                if fields else '')+(f';{text}' if text else '')+final).encode()

    try:
        hwnd = wait_for(lambda: find_window(process.pid))
        wait_for(current)
        phase('initial-query', '\x1b[?u', b'\x1b[?0u')
        phase('push-set-pop', '\x1b[>1u\x1b[>31u\x1b[?u\x1b[<u\x1b[?u'
              '\x1b[=2;2u\x1b[?u\x1b[<u\x1b[?u',
              b'\x1b[?31u\x1b[?1u\x1b[?3u\x1b[?0u')
        phase('all-flags', '\x1b[=31u\x1b[?u', b'\x1b[?31u')
        # Establish modifier state with own-HWND releases, without using SendInput.
        for vk, scan in [(16,42),(16,54),(17,29),(17,285),(18,56),(18,312),(91,347),(92,348)]:
            key(vk, scan, 3)
        locks = (64 if u.GetKeyState(20)&1 else 0) | (128 if u.GetKeyState(144)&1 else 0)
        text_a = '65' if locks&64 else '97'
        key(65, 30); key(65, 30, 2, count=2); key(65, 30, 3)
        expected += code(97, locks, text=text_a)+2*code(97, locks, 2, text_a)+code(97, locks, 3)
        tap(38, 328); expected += code(1, locks, final='A')+code(1, locks, 3, final='A')
        tap(114, 61); expected += code(13, locks, final='~')+code(13, locks, 3, final='~')
        tap(13, 284); expected += code(57414, locks)+code(57414, locks, 3)
        key(17, 29); tap(73,23); key(17,29,3)
        expected += code(57442, locks|4)+code(105, locks|4)+code(105, locks|4,3)+code(57442,locks,3)
        key(16,42); tap(65,30); key(16,42,3)
        expected += code(57441,locks|1)+code(97,locks|1,text='97' if locks&64 else '65',alternates=':65')
        expected += code(97,locks|1,3,alternates=':65')+code(57441,locks,3)
        check()

        phase('unicode-commit', '\x1b[?u', b'\x1b[?31u')
        for scalar in (0x4e2d, 0xd83d, 0xde00, 0xdc00, 0x9b):
            u.SendMessageW(hwnd, 0x102, scalar, 1)
        u.SendMessageW(hwnd, 0x286, 0x6587, 1)  # Unicode WM_IME_CHAR
        expected += code(0,text='20013')+code(0,text='128512')+code(0,text='25991')
        check()
        phase('screen-stacks', '\x1b[?1049h\x1b[?u\x1b[>3u\x1b[?u'
              '\x1b[?1049l\x1b[?u\x1b[?1049h\x1b[?u',
              b'\x1b[?0u\x1b[?3u\x1b[?31u\x1b[?3u')
        tap(65,30); expected += b'A' if locks&64 else b'a'
        tap(27,1); expected += code(27,locks)+code(27,locks,3)
        tap(13,28); expected += b'\r'
        check()
        phase('frozen-key-input', '\x1b[?1049l\x1b[?2026h\x1b[?u', b'\x1b[?31u')
        tap(65,30); expected += code(97,locks,text=text_a)+code(97,locks,3)
        check()
        phase('focus-cleanup', '\x1b[?2026l\x1b[?u', b'\x1b[?31u')
        key(65,30); u.SendMessageW(hwnd,8,0,0); key(65,30,3)
        expected += code(97,locks,text=text_a)+code(97,0,3)
        check()
        phase('resize-preserves-mode', '\x1b[?u', b'\x1b[?31u')
        before = current()['columns']
        assert u.MoveWindow(hwnd,30,30,700,500,True)
        wait_snapshot(current,lambda v:v.get('columns') != before)
        tap(65,30); expected += code(97,locks,text=text_a)+code(97,locks,3)
        check()

        phase('local-copy-paste', '\x1b[2J\x1b[1;1HKEYBOARD COPY LABEL\x1b[?2004h\x1b[?u', b'\x1b[?31u')
        saved = SavedClipboard(hwnd)
        # Grid selection uses Shift in the mouse message itself. Query grid pixels.
        rect = w.RECT(); u.GetClientRect(hwnd,c.byref(rect))
        dimensions = current(); cell_w = (rect.right-2)//dimensions['columns']
        cell_h = (rect.bottom-2)//dimensions['rows']
        start = (cell_h//2+1)<<16 | (cell_w//2+1)
        end = (cell_h//2+1)<<16 | (18*cell_w+1)
        u.SendMessageW(hwnd,0x201,5,start); u.SendMessageW(hwnd,0x200,5,end)
        u.SendMessageW(hwnd,0x202,4,end)
        key(17,29); key(16,42); tap(67,46)
        copied = wait_for(lambda: clipboard_text(hwnd))
        assert copied == 'KEYBOARD COPY LABEL', repr(copied)
        tap(86,47)
        wait_snapshot(current,lambda v: bytes.fromhex(v.get('hex','')).endswith(b'\x1b[201~'))
        key(16,42,3); key(17,29,3)
        expected += code(57442,locks|4)+code(57441,locks|5)
        expected += b'\x1b[200~KEYBOARD COPY LABEL\x1b[201~'
        expected += code(57441,locks|4,3)+code(57442,locks,3)
        check()
        saved.restore(); saved = None
        phase('reset-legacy', '\x1b[?2004l\x1bcKeyboard protocol regression passed\r\n'
              'ConPTY / Unicode / key events / copy-paste / resize\r\n\x1b[?u', b'\x1b[?0u')
        tap(27,1); expected += b'\x1b'; check()
        capture(hwnd,'keyboard-window.png')
        evidence.update(executable_sha256=hashlib.sha256((root/'dist/nemoterm.exe').read_bytes()).hexdigest(),
            peak_private_ws=max(s['private_ws'] for s in samples),
            peak_total_ws=max(s['total_ws'] for s in samples),
            peak_private_commit=max(s['private_commit'] for s in samples), lock_modifiers=locks)
        assert evidence['peak_private_ws'] < 20_000_000, evidence
        (root/'research/keyboard-window-observed.json').write_text(json.dumps(evidence,indent=2))
        print('Native keyboard, ConPTY, copy/paste and resize passed:', evidence)
    finally:
        if saved: saved.restore()
        k.CloseHandle(handle)
        write_snapshot(control,{'stop':True})
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate(); process.wait(timeout=5)
