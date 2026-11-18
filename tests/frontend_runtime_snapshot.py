"""Read loaded module names and process images in the owned native UI fixture.

This queries the frontend only; its shell/agent is allowed to use unrelated
libraries. Snapshot names detect known browser runtimes, not all possible code.
"""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
from thread_snapshot import modules

kernel=c.WinDLL('kernel32',use_last_error=True)
kernel.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)]
kernel.GetProcessId.argtypes=[w.HANDLE];kernel.GetProcessId.restype=w.DWORD
kernel.CloseHandle.argtypes=[w.HANDLE]
WEB_MODULES={'webview2loader.dll','embeddedbrowserwebview.dll','msedge.dll','libcef.dll',
             'chrome.dll','mshtml.dll','xul.dll','qt5webenginecore.dll','qt6webenginecore.dll'}
WEB_PROCESSES={'msedgewebview2.exe','msedge.exe','chrome.exe','chromium.exe','electron.exe',
               'firefox.exe','qtwebengineprocess.exe','cefsharp.browsersubprocess.exe'}


def snapshot(evidence,phase,handle,job,frontend,client):
    frontend=Path(frontend).resolve();client=Path(client).resolve()
    record=dict(phase=phase,frontend_pid=kernel.GetProcessId(handle),modules=[],job_processes=[])
    evidence.setdefault('native_runtime',[]).append(record)
    images=modules(handle)
    record['modules']=sorted(row['name'].casefold() for row in images)
    record['exact_frontend_module']=any(Path(row['path'])==frontend for row in images)
    members=job.member_handles()
    try:
        for member in members:
            path=c.create_unicode_buffer(32768);length=w.DWORD(len(path))
            if not kernel.QueryFullProcessImageNameW(member,0,path,c.byref(length)):
                raise c.WinError(c.get_last_error())
            pid=kernel.GetProcessId(member);assert pid
            name=Path(path.value)
            record['job_processes'].append(dict(pid=pid,image=name.name.casefold(),
                frontend=(name==frontend and pid==record['frontend_pid']),client=name==client))
    finally:
        for member in members:kernel.CloseHandle(member)
    record['job_processes'].sort(key=lambda row:row['pid'])
    record['matched_modules']=sorted(WEB_MODULES.intersection(record['modules']))
    record['matched_processes']=sorted(WEB_PROCESSES.intersection(p['image'] for p in record['job_processes']))
    # Empty or incorrectly targeted observations cannot pass the absence check.
    assert record['exact_frontend_module'] and 'gdi32.dll' in record['modules'],record
    assert any(p['frontend'] for p in record['job_processes']) and any(p['client'] for p in record['job_processes']),record
    assert not record['matched_modules'] and not record['matched_processes'],record
