"""Check live-thread context, target survival and wrong-job rejection."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import uuid
from native_failure_dump import capture_owned_failure_dump, c, k, w
from owned_job import OwnedJob

k.CreateEventW.argtypes = [c.c_void_p, w.BOOL, w.BOOL, w.LPCWSTR]
k.CreateEventW.restype = w.HANDLE
k.SetEvent.argtypes = [w.HANDLE]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--helper', type=Path, required=True)
p.add_argument('--control', type=Path, required=True)
p.add_argument('--destination', type=Path, required=True)
args = p.parse_args()
args.destination.mkdir(parents=True, exist_ok=False)
results = []
for mode in ('live-thread', 'wrong-job', 'already-exited'):
    row = dict(mode=mode); results.append(row)
    token = 'Local\\NemotermDumpControl-'+str(uuid.uuid4())
    go = k.CreateEventW(None, True, False, token)
    if not go: raise c.WinError(c.get_last_error())
    try:
        with OwnedJob() as job, OwnedJob() as other:
            process = job.spawn([str(args.control.resolve()), token, 'normal'],
                                creationflags=subprocess.CREATE_NO_WINDOW)
            if mode == 'already-exited':
                assert k.SetEvent(go)
                assert process.wait(timeout=10) == 23
            row['capture'] = capture_owned_failure_dump(args.helper, process,
                other if mode == 'wrong-job' else job, args.destination/mode)
            assert not row['capture'].get('error') and not row['capture'].get('helper_timeout'), row
            assert not row['capture']['helper_cleanup']['terminated_remaining'], row
            if mode == 'live-thread':
                assert row['capture']['exit_code'] == 0 and process.poll() is None, row
                data=(args.destination/mode/'failure.dmp').read_bytes()
                assert data[:4] == b'MDMP'
                count,offset=struct.unpack_from('<II',data,8)
                streams={kind:(size,rva) for kind,size,rva in
                         (struct.unpack_from('<III',data,offset+12*i) for i in range(count))}
                assert 3 in streams and 4 in streams and 6 not in streams and 17 in streams
                for size,rva in streams.values(): assert rva+size<=len(data)
                size,rva=streams[3]; threads=struct.unpack_from('<I',data,rva)[0]
                assert threads>=1 and size==4+48*threads
                row['thread_contexts']=[]
                for i in range(threads):
                    start=rva+4+48*i
                    tid=struct.unpack_from('<I',data,start)[0]
                    stack_size,stack_rva,context_size,context_rva=struct.unpack_from('<IIII',data,start+32)
                    assert stack_size and stack_rva+stack_size<=len(data)
                    assert context_size>=256 and context_rva+context_size<=len(data)
                    rsp=struct.unpack_from('<Q',data,context_rva+152)[0]
                    rip=struct.unpack_from('<Q',data,context_rva+248)[0]
                    assert rsp and rip
                    row['thread_contexts'].append(dict(tid=tid,rip=hex(rip),rsp=hex(rsp),stack_bytes=stack_size))
            else:
                assert row['capture']['exit_code']==2 and 'dump' not in row['capture'],row
            if mode != 'already-exited':
                assert process.poll() is None
                assert k.SetEvent(go)
                assert process.wait(timeout=10)==23
            row['cleanup']=job.finish(grace=2)
            assert not row['cleanup']['terminated_remaining'],row
        row['passed']=True
    finally:
        k.CloseHandle(go)
        (args.destination/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(row),flush=True)
