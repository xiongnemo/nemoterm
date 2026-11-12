"""Check real ConPTY resizing, rendered Shift selection and bounded history.

All window messages target the newly spawned process. Screenshots use
PrintWindow; the physical keyboard, pointer and foreground focus are untouched.
"""
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, time, read_snapshot, write_snapshot, wait_snapshot,
    memory_sample, wait_for, find_window, capture)
from clipboard_test_utils import SavedClipboard, clipboard_text
import threading

with tempfile.TemporaryDirectory(prefix='nemoterm-reflow-') as directory:
    directory = Path(directory)
    report, control = directory/'report.json', directory/'control.json'
    process = subprocess.Popen([str(root/'dist/nemoterm.exe'), '--cols', '80', '--rows', '20',
        '-e', sys.executable, str(root/'tests/mouse_fixture.py'), str(report), str(control)],
        env=dict(os.environ, NEMOTERM_CONPTY='bundled'), creationflags=subprocess.CREATE_NO_WINDOW)
    handle = k.OpenProcess(0x410, False, process.pid)
    samples, observations, sampling_errors = [], [], []
    done, saved = threading.Event(), None
    def sample():
        while not done.is_set():
            try: samples.append(memory_sample(handle))
            except Exception as error: sampling_errors.append(repr(error)); return
            done.wait(.025)
    sampler = threading.Thread(target=sample)
    sampler.start()
    def current():
        value = read_snapshot(report)
        assert process.poll() is None and not value.get('error'), value
        return value
    def phase(name, sequence):
        write_snapshot(control, {'phase': name, 'sequence': sequence+'\x1b[?2026$p'})
        return wait_snapshot(current, lambda v: v.get('phase') == name and
            b'\x1b[?2026;2$y' in bytes.fromhex(v.get('hex', '')))
    def key(vk, scan, release=False):
        u.SendMessageW(hwnd, 0x101 if release else 0x100, vk,
            1 | scan<<16 | (0xc0000000 if release else 0))
    def resize(cols, rows):
        assert u.MoveWindow(hwnd, 20, 20, frame_w+2+cols*cell_w,
                            frame_h+2+rows*cell_h, True)
        result = wait_snapshot(current, lambda v: (v.get('columns'),v.get('rows')) == (cols,rows))
        # ConPTY can send its own resized frame after reporting the new size.
        time.sleep(.15)
        return result
    def copy_all():
        u.SendMessageW(hwnd, 0x112, 0x0170, 0)  # our system menu: Copy All
        return clipboard_text(hwnd)
    def select(x1,y1,x2,y2):
        rect = w.RECT(); u.GetClientRect(hwnd,c.byref(rect))
        dimensions = current()
        left = (rect.right-dimensions['columns']*cell_w)//2
        top = (rect.bottom-dimensions['rows']*cell_h)//2
        start = (top+y1*cell_h+cell_h//2)<<16 | (left+x1*cell_w+cell_w//2)
        end = (top+y2*cell_h+cell_h//2)<<16 | (left+x2*cell_w+cell_w//2)
        u.SendMessageW(hwnd,0x201,5,start); u.SendMessageW(hwnd,0x200,5,end)
        u.SendMessageW(hwnd,0x202,4,end)
        key(17,29); key(16,42); key(67,46); key(67,46,True)
        key(16,42,True); key(17,29,True)
        return clipboard_text(hwnd)
    def record(name):
        observations.append(dict(phase=name, dimensions=current(), memory=memory_sample(handle)))
    try:
        hwnd = wait_for(lambda: find_window(process.pid))
        wait_for(current)
        saved = SavedClipboard(hwnd)
        outer, client = w.RECT(), w.RECT()
        u.GetWindowRect(hwnd,c.byref(outer)); u.GetClientRect(hwnd,c.byref(client))
        cell_w, cell_h = (client.right-2)//80, (client.bottom-2)//20
        frame_w, frame_h = outer.right-outer.left-client.right, outer.bottom-outer.top-client.bottom
        paragraph = 'REFLOW '+('0123456789'*11)+' 中文 e\u0301 END'
        expected = paragraph+'\r\nHARD BREAK'
        phase('text', '\x1b[?25l\x1b[3J\x1b[2J\x1b[H\x1b[38;2;80;200;230m'
              '\x1b]8;;https://example.org/reflow\x1b\\'+paragraph+
              '\x1b]8;;\x1b\\\x1b[0m\r\nHARD BREAK\x1b[?1003;1006h\x1b[=1u')
        time.sleep(.1)
        assert copy_all().rstrip('\r\n') == expected, repr(copy_all())
        for index, cols in enumerate((40, 100, 32, 80, 40)):
            resize(cols,20)
            text = copy_all().rstrip('\r\n')
            assert text == expected, (cols, repr(text), repr(expected))
            record('text-'+str(cols)+'-'+str(index))
        capture(hwnd,'reflow-narrow.png')
        # The first two complete rendered rows contain ASCII only. Shift must
        # copy through the soft wrap while any-event mouse tracking is active.
        selected = select(0,0,39,1)
        assert selected == paragraph[:80], repr(selected)
        assert bytes.fromhex(current()['hex']) == b'\x1b[?2026;2$y', current()
        observations.append(dict(phase='shift-selection', copied=selected))
        resize(100,20)
        assert copy_all().rstrip('\r\n') == expected
        capture(hwnd,'reflow-wide.png')
        phase('alternate', '\x1b[?1049h\x1b[2J\x1b[2;2HGRID\x1b[?1003;1006h\x1b[=1u')
        resize(50,18)
        assert select(1,1,4,1) == 'GRID'
        phase('main-restored', '\x1b[?1049l')
        assert copy_all().rstrip('\r\n') == expected
        # Bounded default scrollback; repeat width/height changes with enough
        # text to exercise history compression and eviction in a real process.
        phase('history', '\x1b[3J\x1b[2J\x1b[H'+
              ''.join(f'ROW {i:05d} '+('abcdefghij'*7)+'\r\n' for i in range(5000))+'END-OF-HISTORY')
        for index, cols in enumerate((35,100,45,90,40,80)):
            resize(cols,18+index%3)
            text = copy_all().rstrip('\r\n')
            assert text.endswith('END-OF-HISTORY'), repr(text[-100:])
            record('history-'+str(cols))
        assert not sampling_errors, sampling_errors
        result = dict(completed=True, observations=observations,
            executable_sha256=hashlib.sha256((root/'dist/nemoterm.exe').read_bytes()).hexdigest(),
            samples=len(samples),
            **{'peak_'+metric:max(item[metric] for item in samples)
               for metric in ('private_ws','total_ws','private_commit')})
        assert result['peak_private_ws'] < 20_000_000, result
        (root/'research/reflow-window-observed.json').write_text(json.dumps(result,indent=2))
        print('Native reflow, history and Shift selection passed:', result)
    finally:
        if saved: saved.restore()
        done.set(); sampler.join(); k.CloseHandle(handle)
        write_snapshot(control,{'stop':True})
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.terminate(); process.wait(timeout=5)
