"""Compare an actual WSL PTY's Linux winsize to the native Windows text area."""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

from native_test_utils import root, u, wait_for
from protocol_oracle_window import saved_profile
sys.path.insert(0, str(root/'tools'))
import nemoterm_debug as api

BORDER=3

def unix(path):
    return '/mnt/'+path.drive[0].lower()+path.as_posix()[2:]


def exercise(gpu, fixed=False):
    exe=Path(os.environ['NEMOTERM_TEST_EXE']);font=os.environ['NEMOTERM_TEST_FONT'];guest=Path(__file__).with_name('wsl_pixel_geometry_guest.py').resolve()
    folder=root/'research'/('wsl-pty-geometry-'+gpu+('-fixed' if fixed else ''));folder.mkdir()
    stages=['initial','fixed-font'] if fixed else ['initial','grow','zoom']
    def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
    rec=dict(renderer=gpu,executable_sha256=digest(exe),font=font,guest_sha256=digest(guest),checks={},stages={})
    def read(name):
        def available():
            try:return json.loads((folder/(name+'.json')).read_bytes())
            except (FileNotFoundError,PermissionError):return None
        return wait_for(available,timeout=28)
    proc=None;renderer={'gdi':0,'directx':2}[gpu]
    try:
        with saved_profile(dict(NemoWslLinuxPty=1,WindowBorder=BORDER,ScrollBar=0,NemoRenderer=renderer,FontHeight=10,LockSize=2 if fixed else 0,WarnOnClose=0,CloseOnExit=1)) as args:
            env=dict(os.environ,NEMOTERM_CONPTY='bundled');env.pop('NEMOTERM_WSL_PTY_RELAY',None)
            cmd=[str(exe),'--no-tabs',*args,'--automation','--cols','80','--rows','24','--font',font,'-e',shutil.which('wsl.exe'),'--distribution',os.environ['NEMOTERM_TEST_WSL_DISTRO'],'--exec','/usr/bin/python3',unix(guest),unix(folder),*stages]
            proc=subprocess.Popen(cmd,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
            inst=wait_for(lambda:next(iter(api.discover(proc.pid)),None),timeout=25);seat,=inst['sessions'];hwnd=seat['hwnd'];assert seat['renderer']==renderer and seat['window']==hwnd
            def geom():
                s,=api.request(inst['endpoint'])['sessions'];r=w.RECT();assert u.GetClientRect(hwnd,c.byref(r));cols,rows=s['cols'],s['rows'];cw=(r.right-2*BORDER)//cols;ch=(r.bottom-2*BORDER)//rows
                return dict(cols=cols,rows=rows,cw=cw,ch=ch,client=[r.right,r.bottom],winsize=[rows,cols,cols*cw,rows*ch])
            start=rec['startup']=read('startup');assert start['tty'].startswith('/dev/pts/') and start['relay_sha256']==os.environ['NEMOTERM_TEST_RELAY_SHA256'];g=geom();assert (g['cols'],g['rows'])==(80,24)
            rec['checks']['kernel-control']=all(v['sent']==v['slave'] for v in start['kernel_control']);rec['checks']['startup']=start['winsize']==g['winsize']
            for stage in stages:
                if stage in ('grow','fixed-font'):
                    outer=w.RECT();assert u.GetWindowRect(hwnd,c.byref(outer));u.SetWindowPos.argtypes=[w.HWND,w.HWND,c.c_int,c.c_int,c.c_int,c.c_int,w.UINT]
                    dx,dy=(2*g['cols'],4*g['rows']) if fixed else (4*g['cw'],3*g['ch'])
                    before=g
                    assert u.SetWindowPos(hwnd,None,0,0,outer.right-outer.left+dx,outer.bottom-outer.top+dy,0x16)
                    if fixed:
                        g=wait_for(lambda:v if ((v:=geom())['cols'],v['rows'],v['cw'],v['ch'])==(80,24,before['cw']+2,before['ch']+4) else None)
                    else:
                        g=wait_for(lambda:v if ((v:=geom())['cols'],v['rows'])==(84,27) else None)
                if stage=='zoom':
                    u.SendMessageW(hwnd,0x111,0x0940,0);before=g;g=wait_for(lambda:v if ((v:=geom())['cw'],v['ch'])!=(before['cw'],before['ch']) else None)
                (folder/('request-'+stage)).touch();v=read(stage);rec['stages'][stage]=dict(window=g,guest=v)
                rec['checks'][stage+'-vt']=v['cell_grid']==[g['ch'],g['cw'],g['rows'],g['cols']]
                rec['checks'][stage+'-pty']=v['after']==g['winsize']
            (folder/'stop').touch();rec['exit_code']=proc.wait(timeout=15);assert rec['exit_code']==0
    except Exception:rec['error']=traceback.format_exc()
    finally:
        (folder/'stop').touch()
        if proc and proc.poll() is None:
            try: proc.wait(timeout=8)
            except subprocess.TimeoutExpired: proc.terminate();proc.wait(timeout=8);rec['forced_cleanup']=True
        rec['passed']='error' not in rec and not rec.get('forced_cleanup') and len(rec['checks'])==2+len(stages)*2 and all(rec['checks'].values())
        (folder/'geometry.json').write_text(json.dumps(rec,indent=2),encoding='utf8')
    return rec['passed']


if __name__=='__main__':
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    raise SystemExit(not all([exercise(renderer, fixed) for fixed in (False,True) for renderer in ('gdi','directx')]))
