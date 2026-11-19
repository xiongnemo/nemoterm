"""Compare the actual Windows clipboard gesture with retained XTerm clipboard input."""
import argparse
import hashlib
import json
import os
import zipfile

from clipboard_test_utils import SavedClipboard, set_clipboard
from hosted_gesture_input import DesktopInput
from native_test_utils import c, w, u, root, terminal_host, wait_for
from protocol_oracle_window import run
from quote_receipt import expected_native_input, record_quote_pipe
from xterm_paste_lines import ACK, CSI, QUERY, STAGES, TEXT, QUOTE_STAGES, QUOTE_QUERY


def trial(kind, text, renderer, cases, digest, quote=False, literal_next=22, untraced=False):
    label = ('paste-quote-' if quote else 'paste-lines-') + kind
    if untraced: label += '-no-observer'
    stages, query = (QUOTE_STAGES, QUOTE_QUERY) if quote else (STAGES, QUERY)
    details = {'reference_zip_sha256': digest, 'cases': {}}
    profile={'NemoRenderer': renderer-1, 'WarnOnClose': 0}
    if quote:
        details['literal_next']=literal_next
        if literal_next==29: profile['TerminalModes']='LNEXT=V^]'
        else: assert literal_next==22
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
            for name, change in stages.items():
                ref = cases[name]; assert change + query == ref['sequence']
                modes = phase(name, ref['sequence'], None)
                row = details['cases'][name] = {'mode_hex': modes.hex()}
                start = modes + ACK
                desk.chord(0x11, 0x10, ord('V'))
                # Only send the trailing keyboard boundary once the child saw the
                # unique clipboard suffix. The bracket terminator must precede it.
                suffix = b'.' if quote else b'|END.'
                wait_for(lambda: suffix in bytes.fromhex(current()['hex'])[len(start):])
                desk.chord(0x0D); desk.chord(ord('7'))
                snap = wait_for(lambda: (v if (v := current())['hex'].endswith('37') else None))
                received = bytes.fromhex(snap['hex']); assert received.startswith(start)
                row.update(after_query_hex=received[len(start):].hex(), input_api=snap['input_api'],
                           input_cp=snap['input_cp'], expected_paste_hex=ref['paste_hex'], mode_matches=modes.hex()==ref['mode_hex'],
                           paste_and_return_match=received[len(start):] == bytes.fromhex(ref['paste_hex'])+b'\r7')
                if untraced:
                    native, representable = expected_native_input(bytes.fromhex(ref['paste_hex']),literal_next)
                    row.update(native_text_matches=received[len(start):]==native, expected_native_input_hex=native.hex(),
                               reference_representable_by_wide_receiver=representable)
        finally:
            try:
                if desk: desk.restore()
            finally: clip.restore()
    trace_path = root/'research'/(label+'-wire.jsonl')
    try:
        run(label, [], exercise=exercise, barrier=(CSI+'5n', ACK),
            profile=profile, font=os.environ['NEMOTERM_TEST_FONT'], observe_exit=quote)
    except BaseException:
        # Preserve both the original (e.g. shutdown) failure and any incomplete
        # byte observation. A complete trace is still useful after a late exit.
        if quote and not untraced and trace_path.exists():
            try: record_quote_pipe(trace_path.read_bytes(), details, cases, literal_next)
            except Exception as error: details['wire_analysis_error'] = repr(error)
        raise
    else:
        if quote and not untraced:
            record_quote_pipe(trace_path.read_bytes(), details, cases, literal_next)
    finally:
        (root/'research'/(label+'-keyboard.json')).write_text(json.dumps(details, indent=2))
    return all(r['mode_matches'] and (not quote or untraced or r['paste_pipe_matches']) and
               (r['native_text_matches'] if quote else r['paste_and_return_match'])
               for r in details['cases'].values())


def main():
    assert os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
    os.environ.update(NEMOTERM_TEST_INPUT_CP='65001', NEMOTERM_TEST_WIDE_INPUT='1')
    parser=argparse.ArgumentParser();parser.add_argument('--quote',action='store_true')
    parser.add_argument('--exit-control',action='store_true',help='Independent uninstrumented custom-LNEXT window')
    args=parser.parse_args();quote=args.quote
    if args.exit_control:
        assert quote and os.environ.get('NEMOTERM_PROTOCOL_WIRE_TRACE') != '1'
    if quote:
        archive, member, expected = 'xterm412-paste-quote.zip', 'paste-quote/default.json', '3d06c7eec267dc31f6fc8c52e2fc2f0b85de3cb932f4bccca10ec31467c044c1'
    else:
        archive, member, expected = 'xterm412-paste-lines.zip', 'paste-lines/result.json', 'c61a2b31f114b7a7832cbbce395ce251b9855a8ff5382a195b9164c38ea3b342'
    path=root/'testdata/upstream'/archive;digest=hashlib.sha256(path.read_bytes()).hexdigest();assert digest==expected
    with zipfile.ZipFile(path) as z: ref=json.loads(z.read(member))
    assert ref['completed'] and ref['clipboard_hex']==TEXT.encode().hex() and list(ref['cases'])==list(QUOTE_STAGES if quote else STAGES)
    if quote: assert ref['tty_lnext']==22 and ref['quote_profile']=='default'
    renderer={'gdi':1,'directx':3}[os.environ['RENDERER']]
    results=[] if args.exit_control else [trial(kind, text, renderer, ref['cases'], digest, quote) for kind,text in [('crlf',TEXT.replace('\n','\r\n')),('lf',TEXT)]]
    if quote:
        with zipfile.ZipFile(path) as z: custom=json.loads(z.read('paste-quote/custom.json'))
        assert custom['completed'] and custom['tty_lnext']==29 and custom['quote_profile']=='custom'
        assert custom['clipboard_hex']==ref['clipboard_hex'] and custom['xterm_sha256']==ref['xterm_sha256'] and list(custom['cases'])==list(QUOTE_STAGES)
        results.append(trial('custom-lf', TEXT, renderer, custom['cases'], digest, True, 29, untraced=args.exit_control))
    assert all(results), 'See per-phase mode, paste, and Return bytes in the retained keyboard records'


if __name__=='__main__': main()
