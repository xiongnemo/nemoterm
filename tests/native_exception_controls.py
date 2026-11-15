"""Prove exception pass-through, fatal dump capture, and target survival on detach."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import uuid
from native_exception_observer import NativeExceptionObserver, k, c
from owned_job import OwnedJob

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--observer', type=Path, required=True)
p.add_argument('--control', type=Path, required=True)
p.add_argument('--destination', type=Path, required=True)
args = p.parse_args()
args.destination.mkdir(parents=True, exist_ok=False)
results = []
for mode in ('normal', 'crash', 'detach', 'debugger-exit'):
    token = 'Local\\NemotermObserverControl-'+str(uuid.uuid4())
    go = k.CreateEventW(None, True, False, token)
    if not go: raise c.WinError(c.get_last_error())
    row = dict(mode=mode)
    results.append(row)
    observer = None
    try:
        with OwnedJob() as job:
            process = job.spawn([str(args.control.resolve()), token, mode],
                creationflags=subprocess.CREATE_NO_WINDOW)
            observer = NativeExceptionObserver(args.observer, process, job, args.destination/mode)
            if mode == 'detach':
                row['observer'] = observer.close(); observer = None
                assert row['observer']['exit_code'] == 0
                assert process.poll() is None
            elif mode == 'debugger-exit':
                observer.helper.terminate()
                observer.helper.wait(timeout=10)
                row['observer'] = observer.close(); observer = None
                assert process.poll() is None
            if not k.SetEvent(go): raise c.WinError(c.get_last_error())
            process.wait(timeout=15)
            row['process_exit'] = process.returncode
            assert process.returncode == (0xc0000005 if mode == 'crash' else 23), row
            if observer:
                # Let the debugger consume the actual exit event before requesting detach.
                observer.helper.wait(timeout=10)
                row['observer'] = observer.close(); observer = None
                assert row['observer']['exit_code'] == 0, row
            row['cleanup'] = job.finish(grace=2)
            assert not row['cleanup']['terminated_remaining'], row
        events = [json.loads(line) for line in (args.destination/mode/'events.jsonl').read_text().splitlines()]
        assert sum(e['event'] == 'ready' for e in events) == 1
        assert not any(e['event'] == 'observer_error' for e in events)
        exceptions = [e for e in events if e['event'] == 'exception' and not e['initial_attach_break']]
        if mode in ('normal', 'crash'):
            assert any(e['code'] == 0xe1234567 and e['first_chance'] for e in exceptions)
            assert not any(e['code'] == 0xe1234567 and not e['first_chance'] for e in exceptions)
        dumps = list((args.destination/mode).glob('*.dmp'))
        if mode == 'crash':
            assert [e['first_chance'] for e in exceptions if e['code'] == 0xc0000005] == [True, False]
            assert len(dumps) == 1
            data = dumps[0].read_bytes()
            assert data[:4] == b'MDMP'
            count, offset = struct.unpack_from('<II', data, 8)
            streams = [struct.unpack_from('<III', data, offset+12*i) for i in range(count)]
            exception = next(s for s in streams if s[0] == 6)
            assert exception[2]+exception[1] <= len(data)
            assert struct.unpack_from('<I', data, exception[2]+8)[0] == 0xc0000005
            assert struct.unpack_from('<Q', data, exception[2]+24)[0] != 0
            row['dump'] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), streams=count)
        else:
            assert not dumps
        row['passed'] = True
    finally:
        if observer: row['observer_cleanup'] = observer.close()
        k.CloseHandle(go)
        (args.destination/'results.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(row), flush=True)
