"""Compare the actual Windows clipboard gesture with retained XTerm clipboard input."""
import hashlib
import json
import os
import zipfile

from clipboard_test_utils import SavedClipboard, set_clipboard
from hosted_gesture_input import DesktopInput
from native_test_utils import c, w, u, root, terminal_host, wait_for
from protocol_oracle_window import run
from xterm_paste_lines import ACK, CSI, QUERY, STAGES, TEXT


def trial(kind, text, renderer, cases, digest):
    label = 'paste-lines-' + kind
    details = {'reference_zip_sha256': digest, 'cases': {}}
    def exercise(hwnd, phase, current):
        u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND, w.LPCWSTR], w.HANDLE
        details['renderer'] = int(u.GetPropW(hwnd, 'NemotermRenderer') or 0)
        assert details['renderer'] == renderer
        pid = w.DWORD(); assert u.GetWindowThreadProcessId(hwnd, c.byref(pid))
        clip = SavedClipboard(hwnd); desk = None
        try:
            desk = DesktopInput(pid.value, terminal_host(hwnd), hwnd, details.setdefault('keyboard', {}))
            set_clipboard(hwnd, text)
            details['clipboard_utf16le'] = text.encode('utf-16-le').hex()
            for name, change in STAGES.items():
                ref = cases[name]; assert change + QUERY == ref['sequence']
                modes = phase(name, ref['sequence'], None)
                row = details['cases'][name] = {'mode_hex': modes.hex()}
                start = modes + ACK
                desk.chord(0x11, 0x10, ord('V'))
                # Only send the trailing keyboard boundary once the child saw the
                # unique clipboard suffix. The bracket terminator must precede it.
                wait_for(lambda: b'|END.' in bytes.fromhex(current()['hex'])[len(start):])
                desk.chord(0x0D); desk.chord(ord('7'))
                snap = wait_for(lambda: (v if (v := current())['hex'].endswith('37') else None))
                received = bytes.fromhex(snap['hex']); assert received.startswith(start)
                row.update(after_query_hex=received[len(start):].hex(), input_api=snap['input_api'],
                           input_cp=snap['input_cp'], mode_matches=modes.hex()==ref['mode_hex'],
                           paste_and_return_match=received[len(start):] == bytes.fromhex(ref['paste_hex'])+b'\r7')
        finally:
            try:
                if desk: desk.restore()
            finally: clip.restore()
    try:
        run(label, [], exercise=exercise, barrier=(CSI+'5n', ACK),
            profile={'NemoRenderer':renderer-1, 'WarnOnClose':0}, font=os.environ['NEMOTERM_TEST_FONT'])
    finally:
        (root/'research'/(label+'-keyboard.json')).write_text(json.dumps(details, indent=2))
    return all(r['mode_matches'] and r['paste_and_return_match'] for r in details['cases'].values())


def main():
    assert os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
    os.environ.update(NEMOTERM_TEST_INPUT_CP='65001', NEMOTERM_TEST_WIDE_INPUT='1')
    path=root/'testdata/upstream/xterm412-paste-lines.zip'; digest=hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest=='c61a2b31f114b7a7832cbbce395ce251b9855a8ff5382a195b9164c38ea3b342'
    with zipfile.ZipFile(path) as z: ref=json.loads(z.read('paste-lines/result.json'))
    assert ref['completed'] and ref['clipboard_hex']==TEXT.encode().hex() and list(ref['cases'])==list(STAGES)
    renderer={'gdi':1,'directx':3}[os.environ['RENDERER']]
    results=[trial(kind, text, renderer, ref['cases'], digest) for kind,text in [('crlf',TEXT.replace('\n','\r\n')),('lf',TEXT)]]
    assert all(results), 'See per-phase mode, paste, and Return bytes in the retained keyboard records'


if __name__=='__main__': main()
