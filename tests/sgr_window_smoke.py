"""Verify actual styled pixels through the bundled ConPTY and GDI renderer."""
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess, sys,
    tempfile, Path, threading, time, read_snapshot, write_snapshot, memory_sample,
    wait_for, find_window, capture, wait_snapshot)

with tempfile.TemporaryDirectory(prefix='nemoterm-sgr-') as directory:
    directory = Path(directory)
    report, control = directory/'report.json', directory/'control.json'
    process = subprocess.Popen([str(root/'dist/nemoterm.exe'), '--cols', '80', '--rows', '24',
        '-e', sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control)],
        env=dict(os.environ, NEMOTERM_CONPTY='bundled'), creationflags=subprocess.CREATE_NO_WINDOW)
    handle = k.OpenProcess(0x410, False, process.pid)
    samples, stop = [], threading.Event()
    def sampler():
        while not stop.is_set():
            try:
                samples.append(memory_sample(handle))
            except OSError:
                pass
            stop.wait(0.025)
    worker = threading.Thread(target=sampler, daemon=True)
    worker.start()
    evidence = {}
    def current():
        value = read_snapshot(report)
        if value.get('error') or process.poll() is not None:
            raise AssertionError(value)
        return value
    def phase(name, sequence, expected=2):
        write_snapshot(control, {'phase':name, 'sequence':sequence+'\x1b[?2026$p'})
        wait_snapshot(current, lambda value: value.get('phase') == name and
                 f'\x1b[?2026;{expected}$y'.encode() in bytes.fromhex(value.get('hex', '')))
        time.sleep(0.08)
        pixels = capture(hwnd, return_pixels=True)
        evidence[name] = hashlib.sha256(pixels).hexdigest()
        return pixels
    def frame(sgr, text=' '*20):
        return ('\x1b[0m\x1b[?25l\x1b]10;rgb:f/f/f\x07'
                '\x1b]11;rgb:0/0/0\x07\x1b[2J\x1b[H\x1b[2;2H'
                '\x1b['+sgr+'m'+text)
    def colour_mask(pixels, colour):
        return [i//3 for i in range(0, len(pixels), 3) if pixels[i:i+3] == colour]
    try:
        hwnd = wait_for(lambda: find_window(process.pid))
        wait_for(current)
        blank = phase('blank', frame('0'))
        masks = []
        for style in range(1, 6):
            pixels = phase(f'underline-{style}', frame(f'4:{style};58:2::255:0:0'))
            mask = colour_mask(pixels, b'\xff\0\0')
            assert len(mask) > 20, (style, len(mask))
            assert mask not in masks, f'underline style {style} is not distinct'
            masks.append(mask)
        reversed_pixels = phase('reverse-underline', frame('4:5;58:2::255:0:0;7'))
        assert colour_mask(reversed_pixels, b'\xff\0\0') == masks[-1]
        double = phase('legacy-double', frame('21;58;2;255;0;0'))
        assert colour_mask(double, b'\xff\0\0') == masks[1]
        off = phase('underline-reset', frame('4:3;4:0;58:2::255:0:0'))
        assert off == blank
        concealed = phase('conceal', frame('1;3;8;9;4:3;58:2::255:0:0', 'MMMMMMMM'))
        assert concealed == blank, 'concealed glyphs or decorations remain visible'
        regular = phase('regular', frame('0', 'Italic MMMMM and Chinese 中文'))
        italic = phase('italic', frame('3', 'Italic MMMMM and Chinese 中文'))
        assert italic != regular, 'italic font did not change pixels'
        reset_italic = phase('italic-reset', frame('3;23', 'Italic MMMMM and Chinese 中文'))
        assert reset_italic == regular, 'italic reset did not restore pixels'
        normal_m = phase('normal-m-width', frame('0', 'M'))
        italic_m = phase('italic-m-width', frame('3', 'M'))
        rect = w.RECT()
        u.GetClientRect(hwnd, c.byref(rect))
        def ink_width(pixels):
            xs = [i//3 % rect.right for i in range(0, len(pixels), 3)
                  if pixels[i:i+3] != blank[i:i+3] and max(pixels[i:i+3]) > 64]
            return max(xs)-min(xs)+1
        widths = [ink_width(normal_m), ink_width(italic_m)]
        evidence['normal_and_italic_M_width'] = widths
        assert widths[1] >= widths[0]-1, ('italic glyph was squeezed', widths)
        normal_cjk = phase('normal-cjk-width', frame('0', '中'))
        italic_cjk = phase('italic-cjk-width', frame('3', '中'))
        widths = [ink_width(normal_cjk), ink_width(italic_cjk)]
        evidence['normal_and_italic_CJK_width'] = widths
        assert widths[1] >= widths[0]-1, ('italic CJK glyph was squeezed', widths)
        colon = phase('colon-rgb', frame('38:2::12:34:56;48:2::78:90:123', 'TRUE COLOUR'))
        legacy = phase('semicolon-rgb', frame('38;2;12;34;56;48;2;78;90;123', 'TRUE COLOUR'))
        assert colon == legacy, 'colon and semicolon RGB differ through ConPTY'
        indexed = phase('indexed-underline', frame('4:1;58:5:5')+'\x1b]4;5;rgb:f/0/0\x07')
        red = colour_mask(indexed, b'\xff\0\0')
        assert red
        recoloured = phase('palette-change', '\x1b]4;5;rgb:0/f/0\x07')
        assert colour_mask(recoloured, b'\0\xff\0') == red
        assert not colour_mask(recoloured, b'\xff\0\0')
        frozen = phase('styled-sync-freeze', '\x1b[?2026h'+frame('4:3;58:2::0:0:255'), 1)
        assert frozen == recoloured, 'compressed snapshot changed styled pixels'
        released = phase('styled-sync-release', '\x1b[?2026l')
        assert released != frozen and colour_mask(released, b'\0\0\xff')
        gallery = frame('0', 'NEMOTERM TEXT STYLES\r\n\r\n')
        for style, label in enumerate(('single', 'double', 'curly', 'dotted', 'dashed'), 1):
            gallery += f'\x1b[4:{style};58:2::255:80:80m{label}: Unicode 中文 A\u0301\x1b[0m\r\n\r\n'
        gallery += '\x1b[3mItalic: Unicode 中文 A\u0301\x1b[0m\r\n\x1b[38:2::80:180:255mColon RGB colour'
        phase('gallery', gallery)
        capture(hwnd, 'sgr-styles.png')
        evidence.update(peak_private_ws=max(s['private_ws'] for s in samples),
                        peak_total_ws=max(s['total_ws'] for s in samples),
                        executable_sha256=hashlib.sha256((root/'dist/nemoterm.exe').read_bytes()).hexdigest())
        (root/'research/sgr-window-observed.json').write_text(json.dumps(evidence, indent=2))
        assert evidence['peak_private_ws'] < 20_000_000, evidence
        print('Native SGR pixels, colour, conceal, italic and palette tests passed:', evidence)
    finally:
        stop.set()
        worker.join(2)
        k.CloseHandle(handle)
        write_snapshot(control, {'stop': True})
        process.wait(timeout=10)
