"""Only the active tab may change the shared window's maximize or fullscreen state."""
import hashlib,json,os,struct,subprocess,sys,tempfile,time,traceback
from pathlib import Path
from native_test_utils import c,w,u,root,wait_for,wait_snapshot,read_snapshot,write_snapshot
from protocol_oracle_window import saved_profile
from owned_job import OwnedJob
sys.path.insert(0,str(root/'tools'))
import nemoterm_debug as api


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    exe=Path(os.environ['NEMOTERM_TEST_EXE']);font=os.environ['NEMOTERM_TEST_FONT']
    result=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),font=font,steps=[],completed=False)
    cfg=dict(Font=font,FontHeight=12,NemoTabs=1,NemoRenderer=0,LockSize=0,WarnOnClose=0,NoRemoteResize=0,CloseOnExit=1)
    u.GetWindowLongW.argtypes=[w.HWND,c.c_int];u.IsZoomed.argtypes=[w.HWND];u.GetWindowRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
    u.MonitorFromWindow.argtypes=[w.HWND,w.DWORD];u.MonitorFromWindow.restype=w.HANDLE;u.GetMonitorInfoW.argtypes=[w.HANDLE,c.c_void_p]
    u.SetWindowPos.argtypes=[w.HWND,w.HWND,c.c_int,c.c_int,c.c_int,c.c_int,w.UINT]
    class Monitor(c.Structure):_fields_=[('size',w.DWORD),('screen',w.RECT),('work',w.RECT),('flags',w.DWORD)]
    rect=lambda r:[r.left,r.top,r.right,r.bottom]
    try:
        with saved_profile(cfg) as profile,tempfile.TemporaryDirectory() as temp,OwnedJob() as job:
            folder=Path(temp);p=job.spawn([str(exe),*profile,'--tabs','--automation','--cols','64','--rows','16','-e',sys.executable,str(root/'tests/session_fixture.py'),str(folder),'120'],env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1'),creationflags=subprocess.CREATE_NO_WINDOW)
            known=set()
            def child():
                rr=wait_for(lambda:next((f for f in folder.glob('*.report.json') if f not in known and 'hex' in read_snapshot(f)),None));known.add(rr);return rr
            one=child();instance=wait_for(lambda:next(iter(api.discover(p.pid)),None));ep=instance['endpoint'];first,=instance['sessions'];host=first['window']
            assert u.PostMessageW(first['hwnd'],0x111,0x30,0);two=child()
            def active():return next(s for s in api.request(ep)['sessions'] if s['active'])
            second=wait_for(lambda:s if (s:=active())['id']!=first['id'] else None);assert second['window']==host and first['hwnd']!=second['hwnd']; result['seats']=[first,second]
            def state():
                r=w.RECT();assert u.GetWindowRect(host,c.byref(r));return dict(rect=rect(r),frame=u.GetWindowLongW(host,-16)&0x00c40000,zoomed=bool(u.IsZoomed(host)))
            initial=result['initial']=state();m=Monitor();m.size=c.sizeof(m);assert u.GetMonitorInfoW(u.MonitorFromWindow(host,2),c.byref(m));l,t,r,b=result['work']=rect(m.work);x,y,x2,y2=initial['rect'];vertical=dict(initial,rect=[x,t,x2,b]);horizontal=dict(initial,rect=[l,y,r,y2]); full=dict(rect=rect(m.screen),frame=0,zoomed=False);assert len({tuple(s['rect']) for s in [initial,vertical,horizontal,full]})==4
            def step(rr,seat,op,tag,want):
                current=active()['id'];ctl=folder/(rr.name.removesuffix('.report.json')+'.control.json');write_snapshot(ctl,dict(phase=tag,preserve_mouse=True,sequence='\x1b['+op+'t\x1b[5n'))
                reply=wait_snapshot(lambda:read_snapshot(rr),lambda q:q.get('phase')==tag and q.get('hex')=='1b5b306e');row=dict(name=tag,writer=seat['id'],active=current,child=rr.name,op=op,response=reply['hex'],expected=want);result['steps'].append(row)
                end=time.monotonic()+1.2;since=None
                while time.monotonic()<end:
                    got=row['observed']=state();now=time.monotonic()
                    if got==want:
                        if since is None:since=now
                        if now-since>=.23:break
                    else:since=None
                    time.sleep(.025)
                else:raise AssertionError(row)
                assert active()['id']==current;row['passed']=True
            step(one,first,'9;2','inactive-vertical',initial);step(one,first,'10;2','inactive-fullscreen',initial)
            step(two,second,'9;2','active-vertical',vertical);step(one,first,'9;0','hidden-restore-is-ignored',vertical)
            api.request(ep,'key',second['id'],struct.pack('<II',9,2));wait_for(lambda:active()['id']==first['id'])
            step(one,first,'9;3','new-active-horizontal',horizontal);step(one,first,'9;0','new-active-restores-first-size',initial)
            step(one,first,'10;1','foreground-fullscreen',full);step(two,second,'10;0','inactive-cannot-leave',full);step(one,first,'10;0','foreground-restores',initial)
            step(one,first,'9;2','vertical-before-user-resize',vertical)
            manual=dict(initial,rect=[x+9,y+5,x2-19,y2-9]);mx,my,mr,mb=manual['rect'];assert u.SetWindowPos(host,None,mx,my,mr-mx,mb-my,0x14);assert state()==manual
            step(one,first,'9;0','restore-after-user-resize',manual)
            for rr in [one,two]:write_snapshot(folder/(rr.name.removesuffix('.report.json')+'.control.json'),dict(stop=True))
            result['exit_code']=p.wait(timeout=15);result['cleanup']=job.finish();assert result['exit_code']==0 and not result['cleanup']['terminated_remaining'];result['completed']=True
    except Exception:result['error']=traceback.format_exc();raise
    finally:write_snapshot(root/'build/focused-evidence/axis-tabs.json',result)

if __name__=='__main__':main()
