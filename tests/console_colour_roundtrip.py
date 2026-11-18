"""Replay real Codex drawing output; measure native console key records for OSC 10/11."""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

from fixture_io import read_snapshot, write_snapshot

if os.getenv('GITHUB_ACTIONS') != 'true' or os.getenv('RUNNER_ENVIRONMENT') != 'github-hosted':
    raise SystemExit('Only run on a GitHub-hosted Windows runner')

QUERY = b'\x1b]10;?\x1b\\\x1b]11;?\x1b\\'
REPLY = re.compile(rb'\x1b\](10|11);rgb:(?:[0-9a-fA-F]{4}/){2}[0-9a-fA-F]{4}\x1b\\')
HERE = Path(__file__).resolve().parent


def child(folder, prefix, marker):
    k = c.windll.kernel32
    class Key(c.Structure):
        _fields_=[('down',w.BOOL),('repeat',w.WORD),('vk',w.WORD),('scan',w.WORD),('char',w.WORD),('control',w.DWORD)]
    class Event(c.Union):
        _fields_=[('key',Key),('pad',c.c_byte*16)]
    class Record(c.Structure):
        _fields_=[('kind',w.WORD),('event',Event)]
    assert c.sizeof(Record)==20
    k.GetStdHandle.argtypes=[w.DWORD];k.GetStdHandle.restype=w.HANDLE
    k.SetConsoleMode.argtypes=[w.HANDLE,w.DWORD];k.GetConsoleMode.argtypes=[w.HANDLE,c.POINTER(w.DWORD)]
    k.WriteFile.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p]
    k.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD]
    k.ReadConsoleInputW.argtypes=[w.HANDLE,c.POINTER(Record),w.DWORD,c.POINTER(w.DWORD)]
    inp,out=k.GetStdHandle(-10),k.GetStdHandle(-11);oldin=w.DWORD();oldout=w.DWORD();n=w.DWORD()
    assert k.GetConsoleMode(inp,c.byref(oldin)) and k.GetConsoleMode(out,c.byref(oldout))
    assert k.SetConsoleMode(inp,0x98) and k.SetConsoleMode(out,oldout.value|5)
    assert k.SetConsoleOutputCP(65001) and k.SetConsoleCP(65001)
    def emit(raw):assert k.WriteFile(out,raw,len(raw),c.byref(n),None) and n.value==len(raw)
    payload=b'' if prefix=='none' else (HERE/'fixtures/codex-colour-probe'/(prefix+'.vt')).read_bytes()
    if payload:
        meta=json.loads((HERE/'fixtures/codex-colour-probe/source.json').read_bytes())['inputs'][prefix];assert hashlib.sha256(payload).hexdigest()==meta['sha256']
    write_snapshot(folder/'ready.json',dict(pid=os.getpid()));deadline=time.monotonic()+20
    while not (folder/'go').exists():
        if time.monotonic()>deadline:raise TimeoutError('controller did not arm query')
        time.sleep(.005)
    buf=(Record*64)();down=bytearray();batches=[];result=dict(prefix=prefix,prequeued_user_text=marker,input_mode=0x98,output_mode=oldout.value|5)
    if payload:emit(payload)
    start=time.perf_counter();emit(QUERY);result['write_ms']=(time.perf_counter()-start)*1000
    seen=None
    while time.perf_counter()-start < (2 if seen is None else seen+.12):
        status=k.WaitForSingleObject(inp,20)
        if status==258:continue
        assert status==0 and k.ReadConsoleInputW(inp,buf,len(buf),c.byref(n))
        t=time.perf_counter()-start; current=[]
        for r in buf[:n.value]:
            if r.kind!=1:continue
            v=r.event.key;current.append([bool(v.down),v.vk,v.char,v.repeat,v.control]);
            if v.down and 0<v.char<128:down.extend([v.char]*v.repeat)
        batches.append(dict(ms=t*1000,key_records=current))
        if seen is None and len(REPLY.findall(down))>=2:seen=t
    slots=[m[1].decode() for m in REPLY.finditer(down)]
    result.update(ms=seen*1000 if seen is not None else None,batches=batches,keydown_hex=down.hex(),slots=slots,
                  within_client_deadline=seen is not None and seen<=.25,marker_count=down.count(b'k'))
    write_snapshot(folder/'records.json',result)
    assert k.SetConsoleMode(inp,oldin.value) and k.SetConsoleMode(out,oldout.value)


def parent():
    from owned_job import OwnedJob
    from native_test_utils import root,wait_for
    import uuid,winreg
    sys.path.insert(0,str(root/'tools'));import nemoterm_debug as api
    exe=Path(os.environ['NEMOTERM_TEST_EXE']).resolve(strict=True); base=root/'build/focused-evidence/colour-input';base.mkdir(parents=True,exist_ok=True)
    summary=dict(exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),cases=[],errors=[])
    for renderer,number in [('gdi',0),('directx',2)]:
        for prefix in ('none','gdi','directx'):
            for marker in (False,True):
                tag=f'{renderer}-{prefix}-{int(marker)}';folder=base/tag;folder.mkdir();profile='osc-input-'+uuid.uuid4().hex
                key='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER,key) as cfg:
                    for name,value in dict(NemoRenderer=number,WarnOnClose=0,CloseOnExit=1).items():winreg.SetValueEx(cfg,name,0,winreg.REG_DWORD,value)
                case=dict(name=tag);summary['cases'].append(case)
                try:
                    with OwnedJob() as job:
                        proc=job.spawn([str(exe),'--tabs','--automation','-load',profile,'--cols','100','--rows','30','--font',os.environ['NEMOTERM_TEST_FONT'],'-e',sys.executable,str(Path(__file__).resolve()),'child',str(folder),prefix,str(int(marker))],env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
                        wait_for(lambda:read_snapshot(folder/'ready.json'),timeout=20)
                        instance=wait_for(lambda:next(iter(api.discover(proc.pid)),None));session,=instance['sessions'];assert session['renderer']==number
                        if marker:api.request(instance['endpoint'],'input',session['id'],'k')
                        (folder/'go').touch();r=wait_for(lambda:read_snapshot(folder/'records.json'));case.update(ms=r['ms'],slots=r['slots'],within_client_deadline=r['within_client_deadline'],marker_count=r['marker_count']);assert proc.wait(timeout=10)==0
                        case['cleanup']=job.finish();assert not case['cleanup']['terminated_remaining']
                        assert r['slots']==['10','11'] and r['marker_count']==int(marker) and r['within_client_deadline'],case
                except Exception:
                    summary['errors'].append(dict(name=tag,error=traceback.format_exc()))
                finally:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER,key);write_snapshot(base/'summary.json',summary)
    if summary['errors']:raise SystemExit('See full retained per-case records and timings')

if __name__=='__main__':
    if sys.argv[1:2]==['child']:child(Path(sys.argv[2]),sys.argv[3],bool(int(sys.argv[4])))
    else:parent()
