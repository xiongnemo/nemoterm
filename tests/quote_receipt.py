"""Decode recorded clipboard/ConPTY observations; no process, GUI or input access."""
import json
import re


def expected_native_input(paste, literal_next):
    expected = paste+b'\r7'
    try: expected.decode('utf-8'); representable=True
    except UnicodeDecodeError: representable=False
    # A Windows reader operates on Unicode. For quoted multibyte data,
    # also demand a usable native result: a literal-next followed by each
    # scalar, preserving the full text and leaving delimiters/Return alone.
    native=expected
    if not representable:
        data=paste; framed=data.startswith(b'\x1b[200~')
        if framed:
            assert data.endswith(b'\x1b[201~'); data=data[6:-6]
        marker=bytes([literal_next]);assert len(data)%2==0 and data[::2]==marker*(len(data)//2)
        plain=data[1::2].decode('utf-8'); native=b''.join(marker+c.encode('utf-8') for c in plain)
        if framed: native=b'\x1b[200~'+native+b'\x1b[201~'
        native+=b'\r7'
    return native, representable


def record_quote_pipe(wire_jsonl, details, cases, literal_next):
    # Check the frontend at the byte boundary. ReadConsoleW below only returns
    # Unicode: prefixing every UTF-8 byte of a CJK character makes the raw PTY
    # data invalid UTF-8. Keep that separate downstream observation as well.
    events=[json.loads(line) for line in wire_jsonl.splitlines()]
    assert events[-1]['kind']=='closed' and not events[-1]['errors'] and not events[-1]['truncated']
    streams={}
    for e in events:
        if e.get('api')=='WriteFile' and e.get('completed',0)>0:
            b=bytes.fromhex(e['hex']);assert e['success'] and not e['overlapped'] and len(b)==e['completed']
            streams.setdefault(e['handle'],bytearray()).extend(b)
    rows=list(details['cases'].items()); assert list(details['cases'])==list(cases)
    headers=[bytes.fromhex(row['mode_hex'])+b'\x1b[0n' for _,row in rows]
    start=b'\x1b[?2004;'
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
        native, representable = expected_native_input(bytes.fromhex(cases[name]['paste_hex']), literal_next)
        row['reference_representable_by_wide_receiver'] = representable
        row['expected_native_input_hex'] = native.hex()
        row['native_text_matches'] = row['after_query_hex'] == native.hex()

