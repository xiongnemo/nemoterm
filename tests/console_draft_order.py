"""Native input-order witness for one archived Codex startup, only on hosted Windows."""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import uuid
import winreg
from zipfile import ZipFile
from fixture_io import read_snapshot, write_snapshot
from native_test_utils import wait_for
from owned_job import OwnedJob
from codex_image_reference import Record
from console_colour_roundtrip import QUERY, REPLY

ROOT = Path(__file__).resolve().parents[1]
MARK = b'NEMOTERM_CODEX_IMAGE_CTRL_SHIFT_V'
STATUS = b'\x1b[0n'


def source():
    with ZipFile(ROOT/'research/codex-file-clipboard-22ed829.zip') as outer:
        meta, = [r for r in json.loads(outer.read('sources.json')) if 'system-idle' in r['name']]
        data = outer.read(str(meta['id'])+'.zip')
    assert hashlib.sha256(data).hexdigest() == 'ca2c8c7f1875ec1dcd3554c64cd04197cb33a800f0863bd7e3285e2fd60418ac'
    with ZipFile(io.BytesIO(data)) as z:
        n, = [n for n in z.namelist() if n.endswith('/ctrl-shift-v/client-output.log')]
        wire = z.read(n)
    start = wire.index(b'\x1b[c'); end = wire.index(QUERY,start)
    return wire[start:end], dict(artifact=meta['id'], member=n, member_sha256=hashlib.sha256(wire).hexdigest(),
                                 start=start, end=end, query_hex=QUERY.hex())


def child(folder, phase):
    k = c.windll.kernel32; k.GetStdHandle.argtypes=[w.DWORD]; k.GetStdHandle.restype=w.HANDLE
    k.GetConsoleMode.argtypes=[w.HANDLE,c.POINTER(w.DWORD)]; k.SetConsoleMode.argtypes=[w.HANDLE,w.DWORD]
    k.ReadConsoleInputW.argtypes=[w.HANDLE,c.POINTER(Record),w.DWORD,c.POINTER(w.DWORD)]
    k.WriteFile.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p]
    k.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD]
    inp,out=k.GetStdHandle(-10),k.GetStdHandle(-11); im,om,n=w.DWORD(),w.DWORD(),w.DWORD()
    assert c.sizeof(Record)==20 and k.GetConsoleMode(inp,c.byref(im)) and k.GetConsoleMode(out,c.byref(om))
    assert k.SetConsoleMode(inp,0x98) and k.SetConsoleMode(out,om.value|5) and k.SetConsoleCP(65001) and k.SetConsoleOutputCP(65001)
    raw=bytearray(); batches=[]; buf=(Record*64)(); start=time.perf_counter()
    def emit(s):assert k.WriteFile(out,s,len(s),c.byref(n),None) and n.value==len(s)
    def sample():
        res=k.WaitForSingleObject(inp,10)
        if res==258:return
        assert res==0 and k.ReadConsoleInputW(inp,buf,len(buf),c.byref(n))
        events=[]
        for rec in buf[:n.value]:
            if rec.type!=1:
                events.append([rec.type]);continue
            key=rec.event.key; events.append([1,bool(key.down),key.vk,key.scan,key.character,key.repeat,key.control])
            if key.down and key.character:
                raw.extend(chr(key.character).encode('utf-8','surrogatepass')*key.repeat)
        batches.append(dict(seconds=time.perf_counter()-start,events=events))
    prefix,origin=source(); record=dict(origin=origin,phase=phase,expected=MARK.decode(),input_mode=0x98)
    try:
        emit(prefix+b'\x1b[5n'); deadline=time.monotonic()+6
        while STATUS not in raw and time.monotonic()<deadline:sample()
        record['prologue_hex']=raw.hex(); assert raw.endswith(STATUS),record
        raw.clear(); batches.clear(); write_snapshot(folder/'ready.json',dict(pid=os.getpid()))
        wait_for((folder/'go').is_file,timeout=15)
        if phase!='control':emit(QUERY)
        deadline=time.monotonic()+6;end_requested=False;seen_queries=False
        while time.monotonic()<deadline:
            sample(); replies=REPLY.findall(raw)
            if len(replies)==2 and not seen_queries:
                seen_queries=True;write_snapshot(folder/'queries-read.json',dict(slots=[x.decode() for x in replies]))
            body=REPLY.sub(b'',raw)
            # Stop on a barrier, not on the first correct marker. In particular,
            # a permutation is retained as received instead of timing out early.
            if not end_requested and (phase=='control' or seen_queries) and (folder/'sent').is_file() and len(body)>=len(MARK):
                emit(b'\x1b[5n');end_requested=True
            if end_requested and STATUS in raw:break
        record.update(barrier_sent=end_requested,barrier_received=bytes(raw).endswith(STATUS))
        if record['barrier_received']:
            late_until=time.monotonic()+.12
            while time.monotonic()<late_until:sample()
        record.update(raw_hex=raw.hex(),batches=batches)
        clean=REPLY.sub(b'',bytes(raw)); clean=clean.removesuffix(STATUS)
        record['slots']=[s.decode() for s in REPLY.findall(raw)]; record['user_bytes_hex']=clean.hex()
        record['framing']='plain' if clean==MARK else 'bracketed' if clean==b'\x1b[200~'+MARK+b'\x1b[201~' else 'mismatch'
        assert record['barrier_received'] and raw.endswith(STATUS) and record['framing']!='mismatch', record['user_bytes_hex']
        assert record['slots']==([] if phase=='control' else ['10','11']),record['slots']
        record['passed']=True
    finally:
        record.setdefault('batches',batches);record.setdefault('raw_hex',raw.hex());write_snapshot(folder/'records.json',record)
        k.SetConsoleMode(inp,im.value); k.SetConsoleMode(out,om.value)


def parent():
    sys.path.insert(0,str(ROOT/'tools'));import nemoterm_debug as api
    exe=Path(os.environ['NEMOTERM_TEST_EXE']).resolve(strict=True)
    base=ROOT/'build/focused-evidence/draft-order';base.mkdir(parents=True,exist_ok=False)
    results=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),font=os.environ['NEMOTERM_TEST_FONT'],cases=[])
    for renderer,num in [('gdi',0),('directx',2)]:
        reference=None
        for phase in ('control','before','race','after'):
            name=renderer+'-'+phase;folder=base/name;folder.mkdir();profile='draft-'+uuid.uuid4().hex
            key='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
            r=dict(renderer=renderer,phase=phase,passed=False);results['cases'].append(r)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,key) as cfg:
                for k,v in dict(NemoRenderer=num,WarnOnClose=0,CloseOnExit=1).items():winreg.SetValueEx(cfg,k,0,winreg.REG_DWORD,v)
            try:
                with OwnedJob() as job:
                    proc=job.spawn([str(exe),'--tabs','--automation','-load',profile,'--cols','100','--rows','30','--font',results['font'],'-e',sys.executable,__file__,'child',str(folder),phase],env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
                    wait_for(lambda:read_snapshot(folder/'ready.json'),timeout=15)
                    inst=wait_for(lambda:next(iter(api.discover(proc.pid)),None));seat,=inst['sessions'];assert seat['renderer']==num
                    def paste():api.request(inst['endpoint'],'paste',seat['id'],MARK)
                    if phase=='before':paste()
                    (folder/'go').touch()
                    if phase=='after':wait_for(lambda:read_snapshot(folder/'queries-read.json'))
                    if phase!='before':paste()
                    (folder/'sent').touch();obs=wait_for(lambda:read_snapshot(folder/'records.json'),timeout=12)
                    r.update(framing=obs.get('framing'),exit_code=proc.wait(timeout=10),cleanup=job.finish())
                    assert obs.get('passed') and r['exit_code']==0 and not r['cleanup']['terminated_remaining']
                    if phase=='control':reference=r['framing']
                    else:assert r['framing']==reference
                    r['passed']=True
            except Exception:r['error']=traceback.format_exc()
            finally:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER,key);write_snapshot(base/'summary.json',results)
    return int(not all(r['passed'] for r in results['cases']))


if __name__=='__main__':
    assert os.getenv('GITHUB_ACTIONS')=='true' and os.getenv('RUNNER_ENVIRONMENT')=='github-hosted'
    if sys.argv[1:2]==['child']:child(Path(sys.argv[2]),sys.argv[3])
    else:sys.exit(parent())
