"""Compare the actual Windows clipboard gesture with retained XTerm clipboard input."""
import argparse
import hashlib
import json
import os
import re
import zipfile

from clipboard_test_utils import SavedClipboard, set_clipboard
from hosted_gesture_input import DesktopInput
from native_test_utils import c, w, u, root, terminal_host, wait_for
from protocol_oracle_window import run
from xterm_paste_lines import ACK, CSI, QUERY, STAGES, TEXT, QUOTE_STAGES, QUOTE_QUERY


def record_quote_pipe(path, details, cases, literal_next):
    # Check the frontend at the byte boundary. ReadConsoleW below only returns
    # Unicode: prefixing every UTF-8 byte of a CJK character makes the raw PTY
    # data invalid UTF-8. Keep that separate downstream observation as well.
    events=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    assert events[-1]['kind']=='closed' and not events[-1]['errors'] and not events[-1]['truncated']
    streams={}
    for e in events:
        if e.get('api')=='WriteFile' and e.get('completed',0)>0:
            b=bytes.fromhex(e['hex']);assert e['success'] and not e['overlapped'] and len(b)==e['completed']
            streams.setdefault(e['handle'],bytearray()).extend(b)
    rows=list(details['cases'].items()); assert len(rows)==len(cases)
    headers=[bytes.fromhex(row['mode_hex'])+ACK for _,row in rows]
    start=(CSI+'?2004;').encode()
    valid=[(key,bytes(buf)) for key,buf in streams.items() if buf.count(start)==len(headers)]
    assert len(valid)==1, [(key,buf.count(start)) for key,buf in streams.items()]
    key,buf=valid[0]; frames=buf[buf.index(start):].split(start)[1:]; assert len(frames)==len(rows)
    details['pipe_handle']=key
    # A host resize/reset can request its private cursor position. Only separate
    # the exact reply to an earlier, unique token captured on the opposite pipe.
    # Keep the original stream comparison too; an unmatched escape stays in it.
    queries={}; pairs=[]; application=bytearray()
    read_handles={e['handle'] for e in events if e.get('api')=='ReadFile' and e.get('completed',0)>0}
    assert len(read_handles)==1 and key not in read_handles
    for e in events:
        if not e.get('success') or e.get('overlapped') or not e.get('hex'): continue
        chunk=bytes.fromhex(e['hex'])
        if e['api']=='ReadFile':
            for match in re.finditer(rb'\x1b\[\?9001;([1-9][0-9]{0,4})n',chunk):
                token=match[1]; assert token not in queries and int(token)<=65535
                queries[token]=e['event']
        elif e['api']=='WriteFile' and e['handle']==key:
            pos=0
            for match in re.finditer(rb'\x1b\[\?9001;([1-9][0-9]{0,4});([1-9][0-9]*);([1-9][0-9]*)R',chunk):
                before=queries.get(match[1]); response=match[0]
                if before is None or before>=e['event']: continue
                assert all(response not in bytes.fromhex(r['after_query_hex']) for _,r in rows)
                queries[match[1]]=None; pairs.append(dict(query_event=before,reply_event=e['event'],reply_hex=response.hex()))
                application.extend(chunk[pos:match.start()]); pos=match.end()
            application.extend(chunk[pos:])
    details['host_cursor_pairs']=pairs
    appframes=bytes(application).split(start)[1:]; assert len(appframes)==len(frames)
    for (name,row),header,frame,appframe in zip(rows,headers,frames,appframes):
        wire=start+frame; assert wire.startswith(header),(name,wire.hex(),header.hex())
        expected=bytes.fromhex(cases[name]['paste_hex'])+b'\r7'
        payload=wire[len(header):]; row['frontend_pipe_hex']=payload.hex()
        row['frontend_pipe_matches']=payload==expected
        app_frame=start+appframe; assert app_frame.startswith(header)
        row['paste_pipe_hex']=app_frame[len(header):].hex()
        row['paste_pipe_matches']=app_frame[len(header):]==expected
        try: expected.decode('utf-8'); representable=True
        except UnicodeDecodeError: representable=False
        row['reference_representable_by_wide_receiver']=representable
        # A Windows reader operates on Unicode. For quoted multibyte data,
        # also demand a usable native result: a literal-next followed by each
        # scalar, preserving the full text and leaving delimiters/Return alone.
        native=expected
        if not representable:
            data=bytes.fromhex(cases[name]['paste_hex']); framed=data.startswith(b'\x1b[200~')
            if framed:
                assert data.endswith(b'\x1b[201~'); data=data[6:-6]
            marker=bytes([literal_next]);assert len(data)%2==0 and data[::2]==marker*(len(data)//2)
            plain=data[1::2].decode('utf-8'); native=b''.join(marker+c.encode('utf-8') for c in plain)
            if framed: native=b'\x1b[200~'+native+b'\x1b[201~'
            native+=b'\r7'
        row['expected_native_input_hex']=native.hex()
        row['native_text_matches']=row['after_query_hex']==native.hex()


def trial(kind, text, renderer, cases, digest, quote=False, literal_next=22):
    label = ('paste-quote-' if quote else 'paste-lines-') + kind
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
        finally:
            try:
                if desk: desk.restore()
            finally: clip.restore()
    try:
        run(label, [], exercise=exercise, barrier=(CSI+'5n', ACK),
            profile=profile, font=os.environ['NEMOTERM_TEST_FONT'])
        if quote: record_quote_pipe(root/'research'/(label+'-wire.jsonl'), details, cases, literal_next)
    finally:
        (root/'research'/(label+'-keyboard.json')).write_text(json.dumps(details, indent=2))
    return all(r['mode_matches'] and (not quote or r['paste_pipe_matches']) and
               (r['native_text_matches'] if quote else r['paste_and_return_match'])
               for r in details['cases'].values())


def main():
    assert os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
    os.environ.update(NEMOTERM_TEST_INPUT_CP='65001', NEMOTERM_TEST_WIDE_INPUT='1')
    parser=argparse.ArgumentParser();parser.add_argument('--quote',action='store_true');quote=parser.parse_args().quote
    if quote:
        archive, member, expected = 'xterm412-paste-quote.zip', 'paste-quote/default.json', '3d06c7eec267dc31f6fc8c52e2fc2f0b85de3cb932f4bccca10ec31467c044c1'
    else:
        archive, member, expected = 'xterm412-paste-lines.zip', 'paste-lines/result.json', 'c61a2b31f114b7a7832cbbce395ce251b9855a8ff5382a195b9164c38ea3b342'
    path=root/'testdata/upstream'/archive;digest=hashlib.sha256(path.read_bytes()).hexdigest();assert digest==expected
    with zipfile.ZipFile(path) as z: ref=json.loads(z.read(member))
    assert ref['completed'] and ref['clipboard_hex']==TEXT.encode().hex() and list(ref['cases'])==list(QUOTE_STAGES if quote else STAGES)
    if quote: assert ref['tty_lnext']==22 and ref['quote_profile']=='default'
    renderer={'gdi':1,'directx':3}[os.environ['RENDERER']]
    results=[trial(kind, text, renderer, ref['cases'], digest, quote) for kind,text in [('crlf',TEXT.replace('\n','\r\n')),('lf',TEXT)]]
    if quote:
        with zipfile.ZipFile(path) as z: custom=json.loads(z.read('paste-quote/custom.json'))
        assert custom['completed'] and custom['tty_lnext']==29 and custom['quote_profile']=='custom'
        assert custom['clipboard_hex']==ref['clipboard_hex'] and custom['xterm_sha256']==ref['xterm_sha256'] and list(custom['cases'])==list(QUOTE_STAGES)
        results.append(trial('custom-lf', TEXT, renderer, custom['cases'], digest, True, 29))
    assert all(results), 'See per-phase mode, paste, and Return bytes in the retained keyboard records'


if __name__=='__main__': main()
