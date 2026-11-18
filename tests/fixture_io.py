"""Small JSON mailbox for Windows fixture processes.

Windows may deny replacement while another process briefly reads the file.
Keep atomic snapshots, retry that sharing violation, and bound every wait.
"""
import json
import os
import time


def write_snapshot(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value), encoding='utf-8')
    deadline = time.monotonic() + 2
    while True:
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.01)


def read_snapshot(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, PermissionError, json.JSONDecodeError):
        return {}



def stage_sequence(control, text):
    """One controller writes each immutable payload before publishing its short mailbox."""
    if len(text) < 16384:
        return {'sequence':text}
    import hashlib
    data=text.encode('utf-8')
    digest=hashlib.sha256(data).hexdigest()
    path=control.parent/('vt-'+digest+'.bin')
    if not path.exists():
        with path.open('xb') as stream:
            if stream.write(data)!=len(data): raise OSError('Incomplete VT payload write')
    return {'sequence_blob':digest,'sequence_bytes':len(data)}


def load_sequence(control, request):
    if 'sequence_blob' not in request:
        return request.get('sequence','')
    import hashlib
    digest=request['sequence_blob']
    if ('sequence' in request or not isinstance(digest,str) or len(digest)!=64 or
            any(ch not in '0123456789abcdef' for ch in digest)):
        raise ValueError('Invalid fixture payload identity')
    data=(control.parent/('vt-'+digest+'.bin')).read_bytes()
    if len(data)!=request['sequence_bytes'] or hashlib.sha256(data).hexdigest()!=digest:
        raise ValueError('VT payload does not match its published identity')
    return data.decode('utf-8')


def wait_snapshot(reader, predicate=bool, timeout=8):
    """Return the exact snapshot checked by the predicate, reading once per poll."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = reader()
        if predicate(value):
            return value
        time.sleep(0.015)
    raise AssertionError('Timed out waiting for fixture snapshot')
