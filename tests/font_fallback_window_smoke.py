"""Embedded BMP/supplementary icons, grid/clipboard, resize and RTL allocation lifetime."""
import argparse
import uuid
import winreg
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, threading, time, read_snapshot, write_snapshot,
    memory_sample, wait_for, wait_snapshot, find_window, capture)
from clipboard_test_utils import SavedClipboard, clipboard_text

u.GetClientRect.argtypes = u.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.GetGuiResources.argtypes, u.GetGuiResources.restype = [w.HANDLE, w.DWORD], w.DWORD
u.RedrawWindow.argtypes = [w.HWND, c.c_void_p, w.HANDLE, w.UINT]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--rtl-only', action='store_true')
parser.add_argument('--font', default='SarasaTermSC Nerd Font Light')
parser.add_argument('--skip-clipboard', action='store_true',help='Local graphics-only check when clipboard access is unavailable')
options = parser.parse_args()
if options.skip_clipboard and os.environ.get('CI')=='true':parser.error('CI must verify the real clipboard')
name = 'font-fallback-' + uuid.uuid4().hex
keypath = 'Software\\Nemo\\Nemoterm\\Sessions\\' + name
with winreg.CreateKey(winreg.HKEY_CURRENT_USER, keypath) as key:
    winreg.SetValueEx(key, 'LockSize', 0, winreg.REG_DWORD, 2)
    winreg.SetValueEx(key, 'WarnOnClose', 0, winreg.REG_DWORD, 0)
    winreg.SetValueEx(key, 'ScrollbackLines', 0, winreg.REG_DWORD, 0)
exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe'))
evidence = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), requested_font=options.font,
                clipboard_tested=False,completed=False)
try:
    with tempfile.TemporaryDirectory(prefix='nemoterm-symbols-') as directory:
        directory = Path(directory); report, control = directory/'report', directory/'control'
        process = subprocess.Popen([str(exe), '-load', name, '--font', options.font, '--cols', '40', '--rows', '12',
            '-e', sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control)],
            env=dict(os.environ, NEMOTERM_CONPTY='bundled'), creationflags=subprocess.CREATE_NO_WINDOW)
        handle = k.OpenProcess(0x410, False, process.pid)
        samples, stopped = [], threading.Event()
        def sampler():
            while not stopped.is_set():
                try: samples.append(memory_sample(handle))
                except OSError: pass
                stopped.wait(.025)
        worker = threading.Thread(target=sampler, daemon=True); worker.start()
        saved = None
        try:
            hwnd = wait_for(lambda: find_window(process.pid))
            wait_for(lambda: read_snapshot(report))
            def phase(sequence):
                # Unique parser acknowledgement avoids capturing a previous phase.
                phase.counter += 1
                token = str(phase.counter)
                write_snapshot(control, dict(phase=token, sequence=sequence+'\x1b[?2026$p'))
                wait_snapshot(lambda: read_snapshot(report), lambda v:
                    v.get('phase') == token and b'\x1b[?2026;' in bytes.fromhex(v.get('hex', '')))
                time.sleep(.10)
                return capture(hwnd, return_pixels=True)
            phase.counter = 0
            def frame(text):
                return '\x1b[0m\x1b[?25l\x1b]10;#ffffff\x07\x1b]11;#000000\x07\x1b[2J\x1b[2;2H'+text
            def geometry():
                rect = w.RECT(); assert u.GetClientRect(hwnd, c.byref(rect))
                return rect.right, rect.bottom, (rect.right-2)//40, (rect.bottom-2)//12
            def cell(pixels, col, row):
                width, _, cw, ch = geometry()
                return b''.join(pixels[3*((1+row*ch+y)*width+1+col*cw):
                    3*((1+row*ch+y)*width+1+(col+1)*cw)] for y in range(ch))
            if not options.rtl_only:
                initial_ascii = phase(frame('ABC 中文'))
                blank = phase(frame(' X'))
                icons = ['\uf120', '\uf07b', '\U000f0001', '\U000f0002']
                masks = []
                for icon in icons:
                    pixels = phase(frame(icon+'X'))
                    bitmap = cell(pixels, 1, 1)
                    assert any(bitmap), ('missing icon', hex(ord(icon)))
                    assert cell(pixels, 2, 1) == cell(blank, 2, 1), 'fallback shifted or overpainted following X'
                    assert bitmap not in masks, 'different icons rendered the same missing-glyph box'
                    masks.append(bitmap)
                    for selector in ('\ufe0f', '\U000e0100'):
                        with_selector = phase(frame(icon+selector+'X'))
                        assert with_selector == pixels, ('variation selector split the fallback cell',hex(ord(icon)))
                evidence['icons'] = [hex(ord(icon)) for icon in icons]
                # A painted icon that was missing in the main font must be copied as
                # its original Unicode scalar, including supplementary-plane pairs.
                label = 'A'+''.join(icons)+'Z'
                phase(frame(label)+'\x1b[?1000;1006h\x1b[=1u')
                if not options.skip_clipboard:
                    saved = SavedClipboard(hwnd)
                    _, _, cw, ch = geometry()
                    start = (1+ch+ch//2)<<16 | (1+cw+cw//2)
                    end = (1+ch+ch//2)<<16 | (1+6*cw+cw//2)
                    u.SendMessageW(hwnd, 0x201, 5, start); u.SendMessageW(hwnd, 0x200, 5, end)
                    u.SendMessageW(hwnd, 0x202, 4, end)
                    for vk, scan in ((17,29),(16,42),(67,46)): u.SendMessageW(hwnd,0x100,vk,1|(scan<<16))
                    for vk, scan in ((67,46),(16,42),(17,29)): u.SendMessageW(hwnd,0x101,vk,0xc0000001|(scan<<16))
                    assert wait_for(lambda: clipboard_text(hwnd)) == label
                    saved.restore(); saved = None
                    evidence['shift_copy'] = label;evidence['clipboard_tested']=True
                phase(frame('Icons: '+''.join(icons)+'\r\nSarasa 中文 and A\u0301')+'\x1b[?1000l\x1b[=0u')
                capture(hwnd, 'font-fallback.png')
                outer, client = w.RECT(), w.RECT()
                u.GetWindowRect(hwnd, c.byref(outer)); u.GetClientRect(hwnd, c.byref(client))
                base_gdi = u.GetGuiResources(handle,0)
                for i in range(32):
                    scale = (1,1.5,2,1)[i%4]
                    assert u.MoveWindow(hwnd, 20, 20,
                        outer.right-outer.left+round((client.right-2)*(scale-1)),
                        outer.bottom-outer.top+round((client.bottom-2)*(scale-1)), True)
                    pixels = phase(frame(icons[0]+icons[2]+'X'))
                    assert any(cell(pixels,1,1)) and any(cell(pixels,2,1))
                    assert u.GetGuiResources(handle,0) <= base_gdi+8
                    if i == 2: capture(hwnd, 'font-fallback-enlarged.png')
                assert phase(frame('ABC 中文')) == initial_ascii, 'font fallback changed primary text after resize'
                evidence['resize_cycles'] = 32
                # Force separate paints instead of sending a huge burst whose
                # intermediate rows could be skipped by deferred drawing.
                for batch in range(96):
                    text = ''.join(chr(0xf0001+batch*64+i) for i in range(64))
                    phase(frame(text))
                evidence['distinct_symbol_stress'] = 96*64
            # Identical full RTL paints used to leak two temporary GCP buffers
            # per text run. Warm the font mapper, then compare private commit.
            rtl = ''.join(f'\x1b[{row};1H'+('אבגדהוזחטיכלמנסעפצקרשת'*2)[:39] for row in range(1,12))
            phase(frame('')+rtl)
            for i in range(100): assert u.RedrawWindow(hwnd,None,None,0x105)
            before = memory_sample(handle)
            for i in range(5000): assert u.RedrawWindow(hwnd,None,None,0x105)
            after = memory_sample(handle)
            assert after['private_commit']-before['private_commit'] < 2_000_000, (before,after)
            evidence['rtl_repaints'] = dict(count=5000,before=before,after=after)
            evidence.update(peak_private_ws=max(v['private_ws'] for v in samples),
                peak_total_ws=max(v['total_ws'] for v in samples),
                peak_private_commit=max(v['private_commit'] for v in samples))
            assert evidence['peak_private_ws'] < 20_000_000, evidence
            evidence['completed']=True
            print('Native font regression passed (clipboard scope recorded):',evidence)
        finally:
            if saved: saved.restore()
            stopped.set(); worker.join(2); k.CloseHandle(handle)
            write_snapshot(control, {'stop':True})
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.terminate(); process.wait(); raise
finally:
    if sys.exc_info()[0]:evidence['error']=repr(sys.exc_info()[1])
    (root/'research/font-fallback-observed.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
