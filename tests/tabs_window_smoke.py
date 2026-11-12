"""Owned native tab host: routing, four-sided chrome, preview and GPU lifetime."""
from native_test_utils import *
from owned_job import OwnedJob
import argparse
import uuid
import winreg

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--renderer',choices=('gdi','directx','opengl'),default='gdi')
parser.add_argument('--side',choices=('top','bottom','left','right'),default='top')
parser.add_argument('--font',default='Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light')
parser.add_argument('--cols',type=int,default=160)
parser.add_argument('--rows',type=int,default=48)
args=parser.parse_args()
exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
profile='tabs-'+uuid.uuid4().hex
keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
u.GetGuiResources.argtypes,u.GetGuiResources.restype=[w.HANDLE,w.DWORD],w.DWORD
u.GetParent.argtypes,u.GetParent.restype=[w.HWND],w.HWND
u.GetWindowRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
u.GetClientRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
u.IsWindowVisible.argtypes=[w.HWND]
k.GetProcessHandleCount.argtypes=[w.HANDLE,c.POINTER(w.DWORD)]
callback=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
u.EnumChildWindows.argtypes=[w.HWND,callback,w.LPARAM]

def windows(pid,kind,parent=None,visible=False):
    found=[]
    @callback
    def visit(hwnd,_):
        owner=w.DWORD();name=c.create_unicode_buffer(128)
        u.GetWindowThreadProcessId(hwnd,c.byref(owner));u.GetClassNameW(hwnd,name,128)
        if owner.value==pid and name.value==kind and (not visible or u.IsWindowVisible(hwnd)):
            found.append(hwnd)
        return True
    if parent:u.EnumChildWindows(parent,visit,0)
    else:u.EnumWindows(visit,0)
    return found

evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),renderer=args.renderer,
              side=args.side,font=args.font,requested_grid=[args.cols,args.rows],completed=False,checks=[],memory_instrumented=False)
with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:
    for name,value in dict(WarnOnClose=0,CloseOnExit=1,NemoRenderer=
            {'gdi':0,'opengl':1,'directx':2}[args.renderer]).items():
        winreg.SetValueEx(key,name,0,winreg.REG_DWORD,value)
try:
    with tempfile.TemporaryDirectory(prefix='nemoterm-tabs-') as tmp,OwnedJob() as job:
        tmp=Path(tmp);known=set();serial=0;captures=[];hover_session=None
        process=job.spawn([str(exe),'-load',profile,'--tabs','--tab-side',args.side,
            '--cols',str(args.cols),'--rows',str(args.rows),'--font',args.font,'-e',sys.executable,str(root/'tests/session_fixture.py'),str(tmp)],
            env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_UTF8_INPUT='1'),
            creationflags=subprocess.CREATE_NO_WINDOW)
        handle=k.OpenProcess(0x410,False,process.pid)
        try:
            host=wait_for(lambda:next(iter(windows(process.pid,'NemotermHost')),None))
            def new_child(before):
                def launch():
                    for path in tmp.glob('*.launch.json'):
                        value=read_snapshot(path)
                        if value and value['pid'] not in known:return value
                child=wait_for(launch);known.add(child['pid'])
                child['hwnd']=wait_for(lambda:next(iter(set(windows(process.pid,'Nemoterm',host))-set(before)),None))
                child['report']=tmp/f"{child['pid']}.report.json"
                child['control']=tmp/f"{child['pid']}.control.json"
                wait_for(lambda:read_snapshot(child['report']))
                assert child['parent']==process.pid
                assert u.GetParent(child['hwnd'])==host
                wait_for(lambda:u.IsWindowVisible(child['hwnd']))
                return child
            def output(child,sequence):
                global serial
                serial+=1
                write_snapshot(child['control'],dict(phase=serial,sequence=sequence+'\x1b[5n'))
                return wait_snapshot(lambda:read_snapshot(child['report']),lambda v:
                    v.get('phase')==serial and '\x1b[0n'.encode().hex() in v.get('hex',''))
            def barrier(child):
                global serial
                serial+=1;value=read_snapshot(child['control']);value['input_barrier']=serial
                write_snapshot(child['control'],value)
                return wait_snapshot(lambda:read_snapshot(child['report']),lambda v:v.get('input_barrier')==serial)
            def duplicate(child):
                before=windows(process.pid,'Nemoterm',host)
                u.SendMessageW(child['hwnd'],0x111,0x30,0)
                return new_child(before)
            def position(index):
                cr=w.RECT();u.GetClientRect(host,c.byref(cr))
                # Same DIP metrics as the pure geometry test, for a native hit.
                dpi=u.GetDpiForWindow(host);row=(28*dpi+48)//96;preferred=(168*dpi+48)//96
                sidebar=(192*dpi+48)//96
                if args.side=='top':return index*preferred+20,row//2
                if args.side=='bottom':return index*preferred+20,cr.bottom-row//2
                if args.side=='left':return sidebar//2,index*row+row//2
                return cr.right-sidebar//2,index*row+row//2
            def select(child,index):
                x,y=position(index);u.SendMessageW(host,0x201,1,x|(y<<16))
                wait_for(lambda:u.IsWindowVisible(child['hwnd']))
                assert windows(process.pid,'Nemoterm',host,True)==[child['hwnd']]
            def resources():
                count=w.DWORD();assert k.GetProcessHandleCount(handle,c.byref(count))
                return dict(handles=count.value,gdi=u.GetGuiResources(handle,0),user=u.GetGuiResources(handle,1),**memory_sample(handle))
            first=new_child([]);output(first,'\x1b]0;First terminal\x07'+scene('TAB ONE','80;20;20'))
            actual=int(u.GetPropW(first['hwnd'],'NemotermRenderer') or 0)
            evidence['actual_renderer']=actual
            if args.renderer=='directx' and os.environ.get('NEMOTERM_REQUIRE_DIRECTX')=='1':assert actual==3
            surface_class={2:'NemotermOpenGL',3:'NemotermDirect2D'}.get(actual)
            surface=windows(process.pid,surface_class,host) if surface_class else []
            assert len(surface)==(1 if actual>1 else 0)
            initial=resources();second=duplicate(first);output(second,'\x1b]0;Second terminal\x07'+scene('TAB TWO','20;70;20'))
            for child,index in ((first,0),(second,1)):
                select(child,index);token=f"tab-{index};"
                for ch in token:u.SendMessageW(child['hwnd'],0x102,ord(ch),1)
                assert token.encode().hex() in barrier(child)['hex']
                other=first if child is second else second
                assert token.encode().hex() not in barrier(other)['hex']
            assert len(windows(process.pid,'NemotermHost'))==1
            evidence['checks'].append('one host with independent child terminals and native tab hit testing')
            # Measure before any injected capture helper loads into the PID.
            baseline=resources();evidence['initial']=initial;evidence['two_tabs']=baseline;evidence['cycles']=[]
            for i in range(12):
                child=duplicate(second);output(child,scene('TEMPORARY','60;10;60'))
                u.PostMessageW(child['hwnd'],0x10,0,0)
                wait_for(lambda:not u.IsWindow(child['hwnd']))
                select(second,1)
                wait_for(lambda:job.accounting()['active']==5)
                sample=resources();evidence['cycles'].append(sample)
                if surface_class:assert windows(process.pid,surface_class,host)==surface
                assert sample['handles']<=baseline['handles']+6,(baseline,sample)
                assert sample['gdi']<=baseline['gdi']+3,(baseline,sample)
                assert sample['user']<=baseline['user']+2,(baseline,sample)
            evidence['checks'].append('12 create/close cycles retain one shared renderer without handle growth')
            if actual==1 or (actual==3 and os.environ.get('NEMOTERM_REQUIRE_DIRECTX')=='1'):
                assert max(v['private_ws'] for v in [initial,baseline]+evidence['cycles'])<20_000_000
            # Capture after memory samples, recording that subsequent pixels
            # use test instrumentation for hardware readback only.
            from gpu_capture import OwnedGPUCapture
            for child in (first,second):captures.append(OwnedGPUCapture(process.pid,child['hwnd']))
            evidence['pixel_capture_instrumented']=True
            import frida
            hover_session=frida.attach(process.pid)
            hover_script=hover_session.create_script('const ownedHost=ptr("'+hex(host)+'");\n'+(root/'tests/tabs_hover_probe.js').read_text())
            hover_script.load()
            key_script=hover_session.create_script((root/'tests/agent_key_probe.js').read_text());key_script.load()
            def key(child,code,modifiers):
                global serial
                serial+=1;key_script.exports_sync.key(dict(id=serial,key=code,modifiers=modifiers))
                u.PostMessageW(child['hwnd'],0x8322,0,0)
                assert wait_for(lambda:key_script.exports_sync.result())==dict(id=serial)
            key(second,9,[16,17,160,162])
            wait_for(lambda:u.IsWindowVisible(first['hwnd']))
            key(first,9,[17,162])
            wait_for(lambda:u.IsWindowVisible(second['hwnd']))
            evidence['rapid_shell_closes']=[]
            for attempt in range(12):
                before_tabs=set(windows(process.pid,'Nemoterm',host))
                key(second,ord('T'),[16,17,160,162])
                created=wait_for(lambda:next(iter(set(windows(process.pid,'Nemoterm',host))-before_tabs),None))
                wait_for(lambda:u.IsWindowVisible(created))
                key(dict(hwnd=created),ord('W'),[16,17,160,162])
                wait_for(lambda:not u.IsWindow(created))
                select(second,1)
                evidence['closing_shell_attempt']=attempt
                wait_for(lambda:job.accounting()['active']==5)
                evidence['rapid_shell_closes'].append(job.accounting())
            evidence['checks'].append('new, close, next and previous shortcuts act through the terminal input thread')
            faults=hover_session.create_script((root/'tests/session_faults.js').read_text());faults.load()
            for fault in ('process','window'):
                faults.exports_sync.arm(fault)
                before_tabs=set(windows(process.pid,'Nemoterm',host))
                u.SendMessageW(second['hwnd'],0x111,0x30,0)
                assert set(windows(process.pid,'Nemoterm',host))==before_tabs
                assert windows(process.pid,'Nemoterm',host,True)==[second['hwnd']]
                assert faults.exports_sync.status()['hits']
            faults.unload()
            evidence['checks'].append('failed child process or content window creation preserves active tab and renderer')
            # Preview the hidden first tab, then change only its output. The
            # active terminal and input recipient must remain the second tab.
            x,y=position(0);u.SendMessageW(host,0x200,0,x|(y<<16))
            preview=wait_for(lambda:next(iter(windows(process.pid,'NemotermPreview',visible=True)),None))
            before=capture(preview,return_pixels=True)
            output(first,scene('HIDDEN UPDATE','10;20;90'))
            def updated_preview():
                pixels=capture(preview,return_pixels=True)
                return any(pixels[i+2]>180 and pixels[i]<60 and pixels[i+1]<90
                           for i in range(0,len(pixels),3))
            wait_for(updated_preview)
            assert windows(process.pid,'Nemoterm',host,True)==[second['hwnd']]
            r=w.RECT();u.GetClientRect(preview,c.byref(r));assert 0<r.right<=320 and 0<r.bottom<=200
            capture(preview,f'tabs-{args.renderer}-{args.side}-preview.png')
            evidence['checks'].append('bounded hover preview refreshes background output without selecting it')
            u.SendMessageW(host,0x2a3,0,0)
            wait_for(lambda:not u.IsWindowVisible(preview))
            hover_session.detach();hover_session=None
            select(first,0);output(first,scene('FROZEN FIRST','80;10;10'));time.sleep(.08)
            frozen=captures[0].capture(return_pixels=True)
            output(first,'\x1b[?2026h\x1b[2J\x1b[HLATER FRAME')
            select(second,1);select(first,0)
            assert captures[0].capture(return_pixels=True)==frozen
            output(first,'\x1b[?2026l')
            wait_for(lambda:captures[0].capture(return_pixels=True)!=frozen)
            evidence['checks'].append('synchronized pixels survive device transfer between tabs')
            before_full=w.RECT();u.GetWindowRect(host,c.byref(before_full))
            u.SendMessageW(first['hwnd'],0x111,0x180,0)
            u.SendMessageW(first['hwnd'],0x111,0x180,0)
            after_full=w.RECT();u.GetWindowRect(host,c.byref(after_full))
            assert bytes(before_full)==bytes(after_full)
            evidence['checks'].append('fullscreen returns the host to its original rectangle')
            # Resize the host, preserving one visible content window and
            # updating the backend grids of both sessions.
            u.MoveWindow(host,120,100,830,580,True)
            for child,index in ((second,1),(first,0)):
                select(child,index);output(child,'\x1b[18t')
                assert '\x1b[8;'.encode().hex() in read_snapshot(child['report'])['hex']
            evidence['checks'].append('host resize updates both terminal grids')
            if actual==1:capture(host,f'tabs-{args.renderer}-{args.side}-host.png')
            for capture_helper in captures:capture_helper.close()
            captures=[]
            u.PostMessageW(first['hwnd'],0x10,0,0)
            wait_for(lambda:not u.IsWindow(first['hwnd']))
            assert process.poll() is None and u.IsWindow(second['hwnd'])
            output(second,'STILL ALIVE')
            u.PostMessageW(host,0x10,0,0);process.wait(timeout=15)
            assert process.returncode==0,process.returncode
            evidence['owned_job_cleanup']=job.finish(grace=5)
            assert not evidence['owned_job_cleanup']['terminated_remaining']
            evidence['checks'].append('closing original tab preserves sibling; host close drains all processes')
            evidence['completed']=True
        finally:
            if hover_session:hover_session.detach()
            for capture_helper in captures:capture_helper.close()
            if handle:k.CloseHandle(handle)
            evidence.setdefault('owned_job_cleanup',job.finish(grace=0))
finally:
    if sys.exc_info()[0]:evidence['error']=repr(sys.exc_info()[1])
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
    (root/'research'/f'tabs-{args.renderer}-{args.side}-observed.json').write_text(json.dumps(evidence,indent=2))
print('Tabs passed:',args.renderer,args.side,len(evidence['checks']),'checks')
