"""Validate an owned HWND inventory with hidden, child and message-only windows."""
import argparse,ctypes as c,json,subprocess,sys,tempfile,time
from ctypes import wintypes as w
from pathlib import Path
from fixture_io import read_snapshot,write_snapshot
from owned_job import OwnedJob
from handle_snapshot import OwnedHandleSnapshot
from window_snapshot import OwnedWindowSnapshot

def child(folder):
    u=c.WinDLL('user32',use_last_error=True)
    u.CreateWindowExW.argtypes=[w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,c.c_int,c.c_int,c.c_int,c.c_int,
                               w.HWND,w.HMENU,w.HINSTANCE,c.c_void_p]
    u.CreateWindowExW.restype=w.HWND;u.DestroyWindow.argtypes=[w.HWND]
    u.PeekMessageW.argtypes=[c.POINTER(w.MSG),w.HWND,w.UINT,w.UINT,w.UINT]
    u.TranslateMessage.argtypes=[c.POINTER(w.MSG)]
    u.DispatchMessageW.argtypes,u.DispatchMessageW.restype=[c.POINTER(w.MSG)],c.c_ssize_t
    def create(parent=None):
        hwnd=u.CreateWindowExW(0,'STATIC',None,0x40000000 if parent and parent!=-3 else 0,
                              0,0,10,10,parent,None,None,None)
        if not hwnd:raise c.WinError(c.get_last_error())
        return hwnd
    top=create();nested=create(top);message=create(-3);extra=None;phase=None
    try:
        write_snapshot(folder/'ready.json',dict(top=top,child=nested,message=message))
        deadline=time.monotonic()+20;msg=w.MSG()
        while time.monotonic()<deadline:
            while u.PeekMessageW(c.byref(msg),None,0,0,1):
                u.TranslateMessage(c.byref(msg));u.DispatchMessageW(c.byref(msg))
            control=read_snapshot(folder/'control.json')
            if control and control.get('phase')!=phase:
                phase=control['phase']
                if phase=='create':extra=create(top)
                elif phase=='destroy':
                    assert extra and u.DestroyWindow(extra);extra=None
                elif phase=='stop':return
                write_snapshot(folder/'phase.json',dict(phase=phase,extra=extra))
            time.sleep(.01)
        raise TimeoutError('Owned window fixture deadline')
    finally:
        if extra:u.DestroyWindow(extra)
        u.DestroyWindow(message);u.DestroyWindow(top)

def wait(read):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        value=read()
        if value:return value
        time.sleep(.01)
    raise TimeoutError('Owned window fixture did not respond')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--child',type=Path);p.add_argument('--output',type=Path)
    args=p.parse_args()
    if args.child:child(args.child);raise SystemExit(0)
    result=dict(completed=False,snapshots=[])
    with tempfile.TemporaryDirectory(prefix='nemoterm-window-inventory-') as temporary,OwnedJob() as job:
        folder=Path(temporary)
        process=job.spawn([sys.executable,__file__,'--child',str(folder)],creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            ready=wait(lambda:read_snapshot(folder/'ready.json'))
            observer=OwnedWindowSnapshot(OwnedHandleSnapshot(process,job))
            before=observer.snapshot('hidden-and-message-only');result['snapshots'].append(before)
            assert not before['errors'],before['errors']
            windows={row['hwnd']:row for row in before['windows']}
            assert set(ready.values())<=windows.keys()
            assert windows[ready['child']]['parent']==ready['top']
            assert all(not windows[hwnd]['visible'] for hwnd in ready.values())
            write_snapshot(folder/'control.json',dict(phase='create'))
            created=wait(lambda:(v if (v:=read_snapshot(folder/'phase.json')) and v.get('phase')=='create' else None))
            after=observer.snapshot('new-hidden-child');result['snapshots'].append(after)
            assert not after['errors'] and created['extra'] in {row['hwnd'] for row in after['windows']}
            write_snapshot(folder/'control.json',dict(phase='destroy'))
            wait(lambda:(v if (v:=read_snapshot(folder/'phase.json')) and v.get('phase')=='destroy' else None))
            gone=observer.snapshot('child-destroyed');result['snapshots'].append(gone)
            assert not gone['errors'] and created['extra'] not in {row['hwnd'] for row in gone['windows']}
            write_snapshot(folder/'control.json',dict(phase='stop'));process.wait(timeout=5)
            assert process.returncode==0
            try:observer.snapshot('must-reject-exited-owner')
            except RuntimeError:result['exited_owner_rejected']=True
            else:raise AssertionError('Observer accepted an exited owner')
            result['completed']=True
        finally:
            result['cleanup']=job.finish()
            if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    assert not result['cleanup']['terminated_remaining']
    print('Owned window inventory: hidden, child, message-only, create/destroy and exited identity checks passed')
