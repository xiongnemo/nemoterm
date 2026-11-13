"""Owned WM_DROPFILES, Explorer clipboard paths and image-only paste checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import uuid
import winreg
from native_test_utils import c,w,u,k,wait_for
from fixture_io import read_snapshot,write_snapshot
from clipboard_test_utils import SavedClipboard
from owned_job import OwnedJob

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import nemoterm_debug as api
u.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]


def block(data):
    handle=k.GlobalAlloc(0x42,len(data));assert handle
    ptr=k.GlobalLock(handle);assert ptr
    c.memmove(ptr,data,len(data));k.GlobalUnlock(handle)
    return handle


def drop_data(paths,point=(5,5),wide=True):
    return struct.pack('<IiiII',20,*point,0,int(wide))+('\0'.join(paths)+'\0\0').encode('utf-16-le' if wide else 'mbcs')


def quoted(paths,shell):
    result=[]
    for path in paths:
        if shell in ('git-bash','busybox-ash','wsl-bash'):
            path=path.replace('\\','/')
            if shell=='wsl-bash' and path[1:3]==':/':path='/mnt/'+path[0].lower()+path[2:]
            result.append("'"+path.replace("'","'\\''")+"'")
        elif shell=='cmd':
            result.append('"'+path+'\\'*(len(path)-len(path.rstrip('\\')))+'"')
        else:result.append("'"+path.replace("'","''")+"'")
    return ' '.join(result).encode('utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--renderer',choices=('gdi','directx'),default='gdi')
    args=parser.parse_args()
    exe=Path(os.environ.get('NEMOTERM_TEST_EXE',ROOT/'dist/nemoterm.exe')).resolve()
    folder=Path(tempfile.mkdtemp(prefix='file-drop-',dir=ROOT/'build'))
    paths=[str(folder/"space ' 中文 & $name.txt"),str(folder/'folder with spaces')]
    Path(paths[0]).write_text('owned fixture',encoding='utf-8');Path(paths[1]).mkdir()
    result=dict(exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),renderer=args.renderer,
                folder=str(folder),checks=[],cleanup=[])
    detected=json.loads(subprocess.check_output([str(exe),'--list-shells'],creationflags=subprocess.CREATE_NO_WINDOW))
    locations={v['id']:v['path'] for v in detected if v['available']}
    result['shell_argument_checks']={}
    for shell in ('pwsh','powershell','cmd','busybox-ash','git-bash','wsl-bash'):
        profile='drop-'+uuid.uuid4().hex;registry='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,registry) as key:
            for name,value in dict(WarnOnClose=0,CloseOnExit=1,NemoRenderer=2 if args.renderer=='directx' else 0).items():
                winreg.SetValueEx(key,name,0,winreg.REG_DWORD,value)
        saved=None
        try:
            with OwnedJob() as job:
                child_dir=folder/shell;child_dir.mkdir()
                process=job.spawn([str(exe),'-load',profile,'--automation','--tabs','--tab-side',
                    'right' if args.renderer=='directx' else 'top','--shell',shell,'--cols','80','--rows','24',
                    '-e',sys.executable,str(ROOT/'tests/automation_window_smoke.py'),'--child',str(child_dir)],
                    creationflags=subprocess.CREATE_NO_WINDOW)
                instance=wait_for(lambda:next(iter(api.discover(process.pid)),None),timeout=20)
                endpoint=instance['endpoint'];seat=instance['sessions'][0];sid=seat['id'];hwnd=seat['hwnd']
                wait_for(lambda:'NEMOTERM_DEBUG_READY' in api.request(endpoint,'text',sid))
                saved=SavedClipboard(hwnd)
                def received():
                    reports=[read_snapshot(p) for p in child_dir.glob('child-*.json')]
                    return next((bytes.fromhex(r['hex']) for r in reports if r),b'')
                expected=bytearray()
                def check(data,label):
                    expected.extend(data)
                    try:
                        wait_for(lambda:received()==bytes(expected))
                    except BaseException:
                        result['failure']=dict(shell=shell,phase=label,expected_hex=expected.hex(),
                                               received_hex=received().hex(),instance=api.request(endpoint))
                        try:
                            result['failure']['screen']=api.request(endpoint,'text',sid)
                        except Exception as exc:
                            result['failure']['capture_error']=repr(exc)
                        print(json.dumps(result['failure'],ensure_ascii=True),flush=True)
                        raise
                    assert b'\r' not in expected,'Path paste must not submit a command'
                    result['checks'].append(shell+': '+label)
                def clipboard(formats):
                    wait_for(lambda:u.OpenClipboard(hwnd))
                    try:
                        assert u.EmptyClipboard()
                        for fmt,data in formats:assert u.SetClipboardData(fmt,block(data))
                    finally:u.CloseClipboard()
                # Windows marshals WM_DROPFILES to the owned content window.
                handle=block(drop_data(paths))
                assert u.PostMessageW(hwnd,0x233,handle,0)
                pasted=b'\x1b[200~'+quoted(paths,shell)+b'\x1b[201~'
                check(pasted,'file and folder drop preserves shell quoting and bracketed paste')
                k.GlobalFree(handle)
                # Let installed real shells parse the bytes delivered by the
                # terminal. This independently checks quoting, beyond VT bytes.
                expression=received()[6:-6].decode('utf-8')
                if shell in locations and shell in ('pwsh','powershell','busybox-ash','git-bash'):
                    if shell in ('pwsh','powershell'):
                        code="[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); & { $args | ConvertTo-Json -Compress } "+expression
                        command=[locations[shell],'-NoLogo','-NoProfile','-NonInteractive','-Command',code]
                        raw=subprocess.check_output(command,creationflags=subprocess.CREATE_NO_WINDOW,timeout=20)
                        parsed=json.loads(raw.decode('utf-8-sig'))
                        assert parsed==paths,(shell,parsed,paths)
                    else:
                        flags=['ash','-c'] if shell=='busybox-ash' else ['--noprofile','--norc','-c']
                        raw=subprocess.check_output([locations[shell],*flags,"printf '%s\\0' "+expression],
                                                    creationflags=subprocess.CREATE_NO_WINDOW,timeout=20)
                        parsed=raw.decode('utf-8').rstrip('\0').split('\0')
                        assert parsed==[p.replace('\\','/') for p in paths],(shell,parsed,paths)
                    result['shell_argument_checks'][shell]='actual shell parsed exact arguments'
                else:result['shell_argument_checks'][shell]='wire quoting checked; actual shell parsing not exercised'
                # The host also accepts drops, including its tab strip.
                handle=block(drop_data(paths,(10,10)))
                assert u.PostMessageW(seat['window'],0x233,handle,0)
                check(pasted,'tab host routes file drop')
                k.GlobalFree(handle)
                if shell=='pwsh':
                    # Duplicate the owned fixture, then drop onto the inactive
                    # first tab. Its input must not go to the active second tab.
                    u.SendMessageW(hwnd,0x111,0x30,0)
                    seats=wait_for(lambda:(v if len(v:=api.request(endpoint)['sessions'])==2 else None))
                    second=next(v for v in seats if v['id']!=sid)
                    wait_for(lambda:'NEMOTERM_DEBUG_READY' in api.request(endpoint,'text',second['id']))
                    assert second['active']
                    point=(10,10)
                    if args.renderer=='directx':
                        rect=w.RECT();assert u.GetWindowRect(hwnd,c.byref(rect))
                        u.MapWindowPoints.argtypes=[w.HWND,w.HWND,c.c_void_p,w.UINT]
                        u.MapWindowPoints(None,seat['window'],c.byref(rect),2)
                        point=(rect.right+5,10)
                    handle=block(drop_data(paths,point))
                    assert u.PostMessageW(seat['window'],0x233,handle,0)
                    check(pasted,'inactive tab label receives its own file drop')
                    k.GlobalFree(handle)
                    api.request(endpoint,'input',second['id'],'quit\r')
                    wait_for(lambda:len(api.request(endpoint)['sessions'])==1)
                clipboard([(15,drop_data([paths[1]],wide=False))])
                api.request(endpoint,'key',sid,struct.pack('<II',86,3))
                check(b'\x1b[200~'+quoted([paths[1]],shell)+b'\x1b[201~','ANSI copied-file list is converted to Unicode')
                clipboard([(15,drop_data(paths)),(13,'wrong text fallback\0'.encode('utf-16-le'))])
                api.request(endpoint,'key',sid,struct.pack('<II',86,3))
                check(pasted,'Explorer file clipboard takes precedence over fallback text')
                # A tiny generated DIB: image data is never typed as text.
                dib=struct.pack('<IiiHHIIiiII',40,1,1,1,24,0,4,0,0,0,0)+b'\x20\x80\xff\0'
                clipboard([(8,dib)])
                api.request(endpoint,'key',sid,struct.pack('<II',86,3))
                check(b'\x16','image-only paste delegates Ctrl+V to the application')
                clipboard([(8,dib),(13,'normal text\0'.encode('utf-16-le'))])
                api.request(endpoint,'key',sid,struct.pack('<II',86,3))
                check(b'\x1b[200~normal text\x1b[201~','text still uses normal bracketed paste')
                if shell=='pwsh':
                    clipboard([(15,struct.pack('<IiiII',0xfffffffe,0,0,0,1)+b'\0\0')])
                    api.request(endpoint,'key',sid,struct.pack('<II',86,3));time.sleep(.2)
                    assert received()==bytes(expected)
                    result['checks'].append('malformed DROPFILES offset is rejected without input')
                saved.restore();saved=None
                api.request(endpoint,'input',sid,'quit\r');assert process.wait(timeout=15)==0
                cleanup=job.finish();result['cleanup'].append(dict(shell=shell,**cleanup))
                assert not cleanup['terminated_remaining'],cleanup
                print(shell+': passed',flush=True)
        finally:
            if saved:saved.restore()
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,registry)
            write_snapshot(ROOT/f'research/drop-{args.renderer}-observed.json',result)
    result['completed']=True
    write_snapshot(ROOT/f'research/drop-{args.renderer}-observed.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
