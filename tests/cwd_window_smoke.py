"""Directory metadata and session duplication through an owned HWND and ConPTY.

Uses temporary profiles/directories and preserves the clipboard. No user shell
profiles are edited. The child reports the OS cwd, independently of OSC parsing.
"""
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, threading, time, read_snapshot, write_snapshot,
    wait_snapshot, memory_sample, wait_for, find_window, capture)
from clipboard_test_utils import SavedClipboard, clipboard_text
import shutil
import urllib.parse
import uuid
import winreg

exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
observed = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), cases={})
u.GetSystemMenu.argtypes, u.GetSystemMenu.restype = [w.HWND, w.BOOL], w.HMENU
u.GetMenuState.argtypes, u.GetMenuState.restype = [w.HMENU, w.UINT, w.UINT], w.UINT
k.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
profiles, processes, children, handles = [], [], [], []
saved_clipboard = None
samples, stop = [], threading.Event()

def uri(path):
    return 'file:///' + urllib.parse.quote(path.as_posix(), safe='/:')

def make_profile(inherit, directory):
    name = 'cwd-test-' + uuid.uuid4().hex
    keypath = 'Software\\Nemo\\Nemoterm\\Sessions\\' + name
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, keypath) as key:
        winreg.SetValueEx(key, 'WarnOnClose', 0, winreg.REG_DWORD, 0)
        winreg.SetValueEx(key, 'NemoInheritDirectory', 0, winreg.REG_DWORD, int(inherit))
        winreg.SetValueEx(key, 'NemoStartingDirectory', 0, winreg.REG_SZ, str(directory))
        winreg.SetValueEx(key, 'NemoStartingDirectoryUtf8Hex', 0, winreg.REG_SZ,
                         str(directory).encode('utf-8').hex())
    profiles.append(keypath)
    return name

with tempfile.TemporaryDirectory(prefix='nemoterm-cwd-') as temporary:
    base = Path(temporary)
    initial, target = base/'startup 中', base/'reported 中;$(literal)'
    initial.mkdir(); target.mkdir()
    mailbox = base/'mailbox'; mailbox.mkdir()
    # Duplicate Session must find the same executable from a Unicode path.
    executable_dir = base/'executable 中'
    executable_dir.mkdir()
    owned_exe = executable_dir/'nemoterm.exe'
    shutil.copyfile(exe, owned_exe)
    for name in ('conpty.dll', 'OpenConsole.exe'):
        if (exe.parent/name).exists():
            shutil.copyfile(exe.parent/name, executable_dir/name)
    observed['unicode_executable_directory_files'] = sorted(p.name for p in executable_dir.iterdir())

    def new_child(known):
        def probe():
            for path in mailbox.glob('*.launch.json'):
                value = read_snapshot(path)
                if value and value['pid'] not in known:
                    return value
        child = wait_for(probe, timeout=15)
        child['hwnd'] = wait_for(lambda: find_window(child['parent']), timeout=15)
        child['report'] = mailbox/f"{child['pid']}.report.json"
        child['control'] = mailbox/f"{child['pid']}.control.json"
        wait_snapshot(lambda: read_snapshot(child['report']))
        children.append(child)
        return child

    def launch(profile, directory=None):
        args = [str(owned_exe), '-load', profile]
        if directory is not None:
            args += ['--directory', str(directory)]
        args += ['-e', sys.executable, str(root/'tests/cwd_fixture.py'), str(mailbox)]
        process = subprocess.Popen(args, env=dict(os.environ, NEMOTERM_CONPTY='bundled'),
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(process)
        child = new_child({ch['pid'] for ch in children})
        assert child['parent'] == process.pid, child
        return child

    def phase(child, name, sequence):
        write_snapshot(child['control'], dict(phase=name, preserve_mouse=True,
            sequence=sequence+'\x1bP$qcwd-fence\x1b\\'))
        snapshot = wait_snapshot(lambda: read_snapshot(child['report']),
            lambda v: v.get('phase') == name and v.get('hex', '').endswith('1b503024721b5c'))
        assert 'error' not in snapshot, snapshot

    def copied(child):
        u.SendMessageW(child['hwnd'], 0x111, 0x1c0, 0)
        return clipboard_text(child['hwnd'])

    def duplicate(child, expected, name):
        known = {ch['pid'] for ch in children}
        u.SendMessageW(child['hwnd'], 0x111, 0x30, 0)
        duplicate = new_child(known)
        assert Path(duplicate['cwd']) == expected, (name, duplicate['cwd'], str(expected))
        observed['cases'][name] = dict(cwd=duplicate['cwd'], parent=duplicate['parent'])
        handle = k.OpenProcess(0x100000, False, duplicate['parent'])
        assert handle
        try:
            write_snapshot(duplicate['control'], {'stop':True})
            assert k.WaitForSingleObject(handle, 10000) == 0, name
        finally:
            k.CloseHandle(handle)

    try:
        profile = make_profile(True, base)  # CLI directory must override this.
        original = launch(profile, initial)
        assert Path(original['cwd']) == initial, original
        hwnd = original['hwnd']
        saved_clipboard = SavedClipboard(hwnd)
        handle = k.OpenProcess(0x410, False, original['parent']); handles.append(handle)
        assert handle
        def sampler():
            while not stop.is_set():
                samples.append(memory_sample(handle)); stop.wait(.025)
        worker = threading.Thread(target=sampler, daemon=True); worker.start()
        escaped = str(target).replace('\\', '\\\\').replace(';', '\\x3b')
        sequences = {
            'osc7': '\x1b]7;'+uri(target)+'\a',
            'osc9-quoted': '\x1b]9;9;"'+str(target)+'"\x1b\\',
            'osc633': '\x1b]633;P;Cwd='+escaped+';opaque-nonce\a',
            'osc1337': '\x1b]1337;RemoteHost=user@localhost\a\x1b]1337;CurrentDir='+str(target)+'\a',
        }
        for name, sequence in sequences.items():
            phase(original, name, sequence)
            expected_uri = uri(target) if name != 'osc1337' else uri(target).replace('file:///', 'file://localhost/')
            assert copied(original) == expected_uri, (name, copied(original), expected_uri)
            duplicate(original, target, name)
            observed['cases'][name]['copied_uri'] = expected_uri
        phase(original, 'reset', '\x1b[?1049h\x1b[?1049l\x1b[!p\x1bc')
        assert u.MoveWindow(hwnd, 40, 40, 700, 480, True)
        duplicate(original, target, 'reset-resize-retains-directory')
        phase(original, 'remote', '\x1b]7;file://remote.invalid/C:/remote\a')
        assert copied(original) == 'file://remote.invalid/C:/remote'
        duplicate(original, initial, 'remote-directory-does-not-inherit')
        phase(original, 'valid', sequences['osc7'])
        phase(original, 'invalid', '\x1b]7;file:///C:/%00bad\a\x1b]7;file:///C:/'+'a'*17000+'\a')
        duplicate(original, target, 'malformed-and-overflow-keep-last-valid')
        phase(original, 'stress', sequences['osc7']*10000)
        assert copied(original) == uri(target)
        duplicate(original, target, 'ten-thousand-updates')
        phase(original, 'clear', '\x1b]633;P;Cwd=\a')
        menu = u.GetSystemMenu(hwnd, False)
        u.SendMessageW(hwnd, 0x117, menu, 0)
        assert u.GetMenuState(menu, 0x1c0, 0) & 3, 'Empty metadata must disable copy-directory'
        duplicate(original, initial, 'clear-falls-back-to-startup')
        disabled = launch(make_profile(False, initial))
        phase(disabled, 'ignored-for-duplication', sequences['osc7'])
        duplicate(disabled, initial, 'inherit-disabled')
        phase(original, 'final-scene', sequences['osc7']+'\x1b[2J\x1b[HWORKING DIRECTORY INHERITANCE\r\n'
              'OSC 7 / 9;9 / 633 P;Cwd / 1337 CurrentDir\r\n'+str(target)+'\r\n')
        time.sleep(.15); capture(hwnd, 'cwd-window.png')
        observed.update(peak_private_ws=max(s['private_ws'] for s in samples),
            peak_total_ws=max(s['total_ws'] for s in samples),
            peak_private_commit=max(s['private_commit'] for s in samples))
        assert observed['peak_private_ws'] < 20_000_000, observed
        assert observed['peak_total_ws'] < 50_000_000, observed
        assert Path(original['cwd']) == initial
        print('Native directory integration passed:', json.dumps(observed), flush=True)
    finally:
        if saved_clipboard: saved_clipboard.restore()
        stop.set()
        if 'worker' in locals(): worker.join(2)
        for child in children: write_snapshot(child['control'], {'stop':True})
        for child in children:
            handle = k.OpenProcess(0x100000, False, child['parent'])
            if handle:
                if k.WaitForSingleObject(handle, 5000) != 0:
                    u.PostMessageW(child['hwnd'], 0x10, 0, 0)
                    assert k.WaitForSingleObject(handle, 5000) == 0
                k.CloseHandle(handle)
        for process in processes: process.wait(timeout=10)
        for handle in handles: k.CloseHandle(handle)
        for path in profiles: winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
        observed['sample_count'] = len(samples)
        (root/'research/cwd-window-observed.json').write_text(json.dumps(observed, indent=2), encoding='utf-8')
