"""Read loaded module names and process images in the owned native UI fixture.

This queries the frontend only; its shell/agent is allowed to use unrelated
libraries. Snapshot names detect known browser runtimes, not all possible code.
"""
from frontend_runtime_names import WEB_MODULES, WEB_PROCESSES

import ctypes as c
from ctypes import wintypes as w
import time
from pathlib import Path
from thread_snapshot import modules

kernel=c.WinDLL('kernel32',use_last_error=True)
kernel.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)]
kernel.GetProcessId.argtypes=[w.HANDLE];kernel.GetProcessId.restype=w.DWORD
kernel.CloseHandle.argtypes=[w.HANDLE]
kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD]
kernel.WaitForSingleObject.restype=w.DWORD


def snapshot(evidence,phase,handle,job,frontend,client):
    frontend=Path(frontend).resolve();client=Path(client).resolve()
    record=dict(phase=phase,frontend_pid=kernel.GetProcessId(handle),modules=[],job_processes=[])
    evidence.setdefault('native_runtime',[]).append(record)
    images=modules(handle)
    record['modules']=sorted(row['name'].casefold() for row in images)
    record['exact_frontend_module']=any(Path(row['path'])==frontend for row in images)
    # Job membership, process exit and image-name availability are not atomic.
    # Keep every incomplete enumeration, including its identities and errors;
    # only a complete fresh enumeration can satisfy the snapshot assertion.
    record['process_enumerations']=[]
    deadline=time.monotonic()+2
    while True:
        missing=[];rows=[]
        record['process_enumerations'].append(dict(processes=rows,unavailable=missing))
        members=job.member_handles(unavailable=missing)
        try:
            for member in members:
                pid=kernel.GetProcessId(member);assert pid
                path=c.create_unicode_buffer(32768);length=w.DWORD(len(path))
                if not kernel.QueryFullProcessImageNameW(member,0,path,c.byref(length)):
                    error=c.get_last_error();state=kernel.WaitForSingleObject(member,0)
                    missing.append(dict(pid=pid,operation='QueryFullProcessImageNameW',winerror=error,
                                        wait_state=state))
                    if state!=0 and error not in (5,31,299):raise c.WinError(error)
                    continue
                name=Path(path.value)
                rows.append(dict(pid=pid,image=name.name.casefold(),
                                 frontend=(name==frontend and pid==record['frontend_pid']),client=name==client))
                assert rows[-1]['image'] not in WEB_PROCESSES,record
        finally:
            for member in members:kernel.CloseHandle(member)
        if not missing:
            record['job_processes']=rows
            break
        if time.monotonic()>=deadline:raise AssertionError(('incomplete job process snapshot',record))
        time.sleep(.05)
    record['job_processes'].sort(key=lambda row:row['pid'])
    record['matched_modules']=sorted(WEB_MODULES.intersection(record['modules']))
    record['matched_processes']=sorted(WEB_PROCESSES.intersection(p['image'] for p in record['job_processes']))
    # Empty or incorrectly targeted observations cannot pass the absence check.
    assert record['exact_frontend_module'] and 'gdi32.dll' in record['modules'],record
    assert any(p['frontend'] for p in record['job_processes']) and any(p['client'] for p in record['job_processes']),record
    assert not record['matched_modules'] and not record['matched_processes'],record
