"""Native overflow navigation and visible active-tab invariants in an owned host."""
from native_test_utils import *
from owned_job import OwnedJob
import argparse
import uuid
import winreg
from thread_snapshot import OwnedThreadSnapshot

sys.path.insert(0,str(root/'tools'))
import nemoterm_debug as api

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--side',choices=('top','bottom','left','right'),default='top')
args=parser.parse_args()
exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
profile='tabs-overflow-'+uuid.uuid4().hex
keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
u.GetWindowTextW.argtypes=[w.HWND,w.LPWSTR,c.c_int]
u.GetClientRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
u.GetWindowRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
u.ClientToScreen.argtypes=[w.HWND,c.POINTER(w.POINT)]
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    side=args.side,completed=False,checks=[],injected=False,global_input=False,
    keyboard_transport='public automation API')
with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:
    for name,value in dict(WarnOnClose=0,CloseOnExit=1,NemoRenderer=0).items():
        winreg.SetValueEx(key,name,0,winreg.REG_DWORD,value)
try:
    with tempfile.TemporaryDirectory(prefix='nemoterm-overflow-') as tmp,OwnedJob() as job:
        tmp=Path(tmp);known=set();serial=0
        process=job.spawn([str(exe),'-load',profile,'--automation','--tabs','--tab-side',args.side,
            '--cols','40','--rows','10','-e',sys.executable,str(root/'tests/session_fixture.py'),str(tmp)],
            env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_UTF8_INPUT='1'),
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            hwnd=wait_for(lambda:find_window(process.pid));host=terminal_host(hwnd)
            instance=wait_for(lambda:next(iter(api.discover(process.pid)),None))
            assert instance['pid']==process.pid
            endpoint=instance['endpoint']
            evidence.update(pid=process.pid,endpoint=endpoint)
            u.MoveWindow(host,100,100,400,240,True)
            def title():
                buf=c.create_unicode_buffer(128);u.GetWindowTextW(host,buf,128);return buf.value
            def output(child,text):
                global serial
                serial+=1;write_snapshot(child['control'],dict(phase=serial,sequence=text+'\x1b[5n'))
                return wait_snapshot(lambda:read_snapshot(child['report']),lambda v:
                    v.get('phase')==serial and bytes.fromhex(v.get('hex','')).endswith(b'\x1b[0n'))
            def new_child(index):
                def launch():
                    for path in tmp.glob('*.launch.json'):
                        value=read_snapshot(path)
                        if value and value['pid'] not in known:return value
                child=wait_for(launch);known.add(child['pid'])
                child['hwnd']=wait_for(lambda:find_window(process.pid))
                item=wait_for(lambda:next((s for s in api.request(endpoint)['sessions']
                    if s['hwnd']==child['hwnd']),None))
                assert item['active'] and item['window']==host
                child['session']=item['id']
                child['report']=tmp/f"{child['pid']}.report.json"
                child['control']=tmp/f"{child['pid']}.control.json"
                child['title']=f'Overflow tab {index}'
                wait_for(lambda:read_snapshot(child['report']))
                output(child,'\x1b]0;'+child['title']+'\x07\x1b[?25l\x1b[2J\x1b[H'+child['title'])
                wait_for(lambda:title()==child['title']);return child
            def active_stripe():
                cr=w.RECT();u.GetClientRect(host,c.byref(cr))
                child=find_window(process.pid)
                r=w.RECT();u.GetWindowRect(child,c.byref(r))
                origin=w.POINT();u.ClientToScreen(host,c.byref(origin))
                # Inspect the native strip outside the content child. The
                # selected fill must remain visible, regardless of item widths.
                image=capture(host,return_pixels=True)
                for y in range(cr.bottom):
                    for x in range(cr.right):
                        if r.left<=origin.x+x<r.right and r.top<=origin.y+y<r.bottom:continue
                        offset=(y*cr.right+x)*3
                        if image[offset:offset+3]==bytes((64,68,76)):return (x,y)
                return None
            def visible(child):
                wait_for(lambda:find_window(process.pid)==child['hwnd'] and title()==child['title'])
                wait_for(lambda:any(s['id']==child['session'] and s['active'] and s['title']==child['title']
                    for s in api.request(endpoint)['sessions']))
                wait_for(active_stripe)
            children=[new_child(0)]
            for index in range(1,10):
                u.SendMessageW(children[-1]['hwnd'],0x111,0x30,0)
                children.append(new_child(index));visible(children[-1])
            evidence['checks'].append('each newly appended tab is visible despite overflow')
            evidence['session_ids']=[child['session'] for child in children]
            assert len(set(evidence['session_ids']))==10
            assert len(api.request(endpoint)['sessions'])==10
            def key(child,reverse=False):
                api.request(endpoint,'key',child['session'],struct.pack('<II',9,2|int(reverse)))
            current=children[-1]
            for child in children:
                key(current);visible(child);current=child
            evidence['checks'].append('keyboard cycles all ten tabs and reveals the selected item')
            for index in range(8,4,-1):
                key(current,True);current=children[index];visible(current)
            u.PostMessageW(children[0]['hwnd'],0x10,0,0)
            wait_for(lambda:not u.IsWindow(children[0]['hwnd']))
            visible(current)
            evidence['checks'].append('closing a preceding background tab keeps the active tab visible')
            # Scroll the strip independently, then return keyboard selection.
            first=capture(host,return_pixels=True)
            u.SendMessageW(host,0x20a,120<<16,0)
            wait_for(lambda:capture(host,return_pixels=True)!=first)
            key(current);current=children[6];visible(current)
            evidence['checks'].append('wheel scroll and subsequent keyboard navigation restore visibility')
            # Middle-click the active fill, away from text and close buttons.
            x,y=wait_for(active_stripe)
            u.SendMessageW(host,0x208,0,x|(y<<16))
            wait_for(lambda:not u.IsWindow(current['hwnd']))
            wait_for(active_stripe)
            evidence['checks'].append('middle-click closes the hit tab and reveals a live successor')
            capture(host,f'tabs-overflow-{args.side}.png')
            close_started=time.monotonic()
            assert u.PostMessageW(host,0x10,0,0)
            try:
                assert process.wait(timeout=15)==0
                evidence['close_seconds']=time.monotonic()-close_started
            except subprocess.TimeoutExpired:
                evidence['close_seconds']=time.monotonic()-close_started
                evidence['host_still_exists']=bool(u.IsWindow(host))
                try:
                    evidence['timeout_threads']=OwnedThreadSnapshot(process,job).snapshot('close-timeout')
                except Exception as error:
                    evidence['snapshot_error']=repr(error)
                raise
            assert api.discover(process.pid)==[]
            evidence['owned_job_cleanup']=job.finish(grace=5)
            assert not evidence['owned_job_cleanup']['terminated_remaining']
            evidence['completed']=True
        finally:
            evidence.setdefault('owned_job_cleanup',job.finish(grace=0))
finally:
    if sys.exc_info()[0]:evidence['error']=repr(sys.exc_info()[1])
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
    (root/'research'/f'tabs-overflow-{args.side}-observed.json').write_text(json.dumps(evidence,indent=2))
print('Native overflow passed:',args.side,len(evidence['checks']),'checks')
