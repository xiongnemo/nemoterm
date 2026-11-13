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
parser.add_argument('--dense-clusters',action='store_true')
parser.add_argument('--workload-memory',action='store_true',
                    help='sample the full process tree during dense history and resize before instrumentation')
parser.add_argument('--allocation-census',action='store_true',
                    help='CI-only injected diagnostic; requires --workload-memory and exits 2, never acceptance')
args=parser.parse_args()
if args.allocation_census and (not args.workload_memory or os.environ.get('CI')!='true'):
    parser.error('--allocation-census requires --workload-memory on a dedicated CI runner')
if args.allocation_census:faulthandler.dump_traceback_later(180,exit=True)
if args.workload_memory:args.dense_clusters=True
prefix='allocation-tabs' if args.allocation_census else 'workload-tabs' if args.workload_memory else 'cluster-tabs' if args.dense_clusters else 'tabs'
base_scene=scene
dense_memory_phase=args.dense_clusters
def scene(text,colour):
    result=base_scene(text,colour)
    if not dense_memory_phase:return result
    cols,rows=evidence['actual_grid']
    unit='e\u0301 \U0001f469\u200d\U0001f4bb \U0001f44d\U0001f3fd 1\ufe0f\u20e3 \u1100\u1161\u11a8 אבג ابت '
    line=unit*max(1,(cols-1)//22)
    return '\x1b[?2027h'+result+'\x1b[H'+'\r\n'.join(line for _ in range(max(1,rows-1)))
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
              side=args.side,font=args.font,requested_grid=[args.cols,args.rows],dense_clusters=args.dense_clusters,
              completed=False,checks=[],memory_instrumented=args.allocation_census)
if args.allocation_census:evidence.update(diagnostic_completed=False,memory_acceptance=False)
with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:
    for name,value in dict(WarnOnClose=0,CloseOnExit=1,NemoRenderer=
            {'gdi':0,'opengl':1,'directx':2}[args.renderer]).items():
        winreg.SetValueEx(key,name,0,winreg.REG_DWORD,value)
    if args.workload_memory:winreg.SetValueEx(key,'ScrollbackLines',0,winreg.REG_DWORD,2000)
try:
    with tempfile.TemporaryDirectory(prefix='nemoterm-tabs-') as tmp,OwnedJob() as job:
        tmp=Path(tmp);known=set();serial=0;captures=[];hover_session=None;memory_sampler=None;census_observer=None
        process=job.spawn([str(exe),'-load',profile,'--tabs','--tab-side',args.side,
            '--cols',str(args.cols),'--rows',str(args.rows),'--font',args.font,'-e',sys.executable,str(root/'tests/session_fixture.py'),str(tmp)],
            env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_UTF8_INPUT='1'),
            creationflags=subprocess.CREATE_NO_WINDOW)
        handle=k.OpenProcess(0x410,False,process.pid)
        try:
            if args.workload_memory:
                from tab_workload_memory import TabMemorySampler,exercise as memory_exercise
                memory_sampler=TabMemorySampler(process.pid,exe,injected=args.allocation_census)
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
                for visible_hwnd in windows(process.pid,'Nemoterm',host,True):
                    u.RedrawWindow(visible_hwnd,None,None,0x185)
                count=w.DWORD();assert k.GetProcessHandleCount(handle,c.byref(count))
                if memory_sampler and os.environ.get('NEMOTERM_TEST_MEMORY_REGIONS')=='1':
                    phase=memory_sampler.phase
                    if phase in ('history-0','history-1','frame-0','frame-23','settled'):
                        from working_set_regions import private_regions
                        evidence.setdefault('memory_regions',{})[phase]=private_regions(handle)
                return dict(handles=count.value,gdi=u.GetGuiResources(handle,0),user=u.GetGuiResources(handle,1),
                            injected=args.allocation_census,**memory_sample(handle))
            first=new_child([])
            size=read_snapshot(first['report']);evidence['actual_grid']=[size['columns'],size['rows']]
            output(first,'\x1b]0;First terminal\x07'+scene('TAB ONE','80;20;20'))
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
            evidence['live_temporary_tabs']=[]
            if args.dense_clusters:
                # Warm lazy window/IME/menu resources before comparing handle
                # counts. Retain both live and post-close memory observations.
                child=duplicate(second);output(child,scene('WARMUP','60;10;60'))
                evidence['live_temporary_tabs'].append(resources())
                u.PostMessageW(child['hwnd'],0x10,0,0)
                wait_for(lambda:not u.IsWindow(child['hwnd']))
                select(second,1);wait_for(lambda:job.accounting()['active']==5)
                evidence['warmup']=resources()
            baseline=resources();evidence['initial']=initial;evidence['two_tabs']=baseline;evidence['cycles']=[]
            for i in range(12):
                child=duplicate(second);output(child,scene('TEMPORARY','60;10;60'))
                if args.dense_clusters:evidence['live_temporary_tabs'].append(resources())
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
            memory_observations=[initial,baseline]+evidence['cycles']+evidence['live_temporary_tabs']
            evidence['peak_private_ws']=max(v['private_ws'] for v in memory_observations)
            if not args.workload_memory and (actual==1 or (actual==3 and os.environ.get('NEMOTERM_REQUIRE_DIRECTX')=='1')):
                assert evidence['peak_private_ws']<20_000_000,evidence['peak_private_ws']
            if args.workload_memory:
                if args.allocation_census:
                    from allocation_census import AllocationCensus
                    census_observer=AllocationCensus(process.pid,handle,
                        root/'research'/f'{prefix}-{args.renderer}-{args.side}-census.json')
                    census_observer.result['executable_sha256']=evidence['executable_sha256']
                    census_observer.start()
                evidence['workload']=memory_exercise(memory_sampler,first,second,output,select,resources,host,scene)
                memory=memory_sampler.stop();memory_sampler=None
                memory_path=root/'research'/f'{prefix}-{args.renderer}-{args.side}-memory.json'
                memory_path.write_text(json.dumps(memory,indent=2),encoding='utf-8')
                assert not memory['errors'],memory['errors']
                assert memory['sample_count']>=20,memory['sample_count']
                stable=[s for s in memory['samples'] if s['phase']!='startup']
                assert stable and all(s['groups']['frontend']['count']==1 and
                    s['groups']['hosts']['count']==2 and s['groups']['clients']['count']==2
                    for s in stable),'Stable two-tab workload omitted an owned process'
                evidence['process_tree_memory']={k:v for k,v in memory.items() if k!='samples'}
                evidence['peak_private_ws']=max(evidence['peak_private_ws'],memory['peaks']['frontend']['private_ws'])
                evidence['memory_limit_required']=actual in (1,3)
                evidence['memory_limit_passed']=None if args.allocation_census else evidence['peak_private_ws']<20_000_000
                if args.allocation_census:
                    evidence['allocation_census']=census_observer.freeze()
                    census_observer.close();census_observer=None
                    u.PostMessageW(host,0x10,0,0);process.wait(timeout=15)
                    assert process.returncode==0,process.returncode
                    evidence['owned_job_cleanup']=job.finish(grace=5)
                    assert not evidence['owned_job_cleanup']['terminated_remaining']
                    evidence['diagnostic_completed']=True
                    print('Allocation diagnostic complete; memory acceptance was not evaluated',flush=True)
                    # Dedicated diagnostic CI recognizes this explicit outcome.
                    # Ordinary acceptance workflows must not turn green here.
                    raise SystemExit(2)
            if args.dense_clusters:
                dense_memory_phase=False
                output(first,scene('TAB ONE','80;20;20'));output(second,scene('TAB TWO','20;70;20'))
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
            capture(preview,f'{prefix}-{args.renderer}-{args.side}-preview.png')
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
            evidence['first_tab_close']=dict(frontend_exit=process.poll(),sibling_alive=bool(u.IsWindow(second['hwnd'])))
            assert evidence['first_tab_close']['frontend_exit'] is None and evidence['first_tab_close']['sibling_alive'],evidence['first_tab_close']
            output(second,'STILL ALIVE')
            u.PostMessageW(host,0x10,0,0);process.wait(timeout=15)
            assert process.returncode==0,process.returncode
            evidence['owned_job_cleanup']=job.finish(grace=5)
            assert not evidence['owned_job_cleanup']['terminated_remaining']
            evidence['checks'].append('closing original tab preserves sibling; host close drains all processes')
            if args.workload_memory and evidence['memory_limit_required']:
                assert evidence['memory_limit_passed'],evidence['peak_private_ws']
            evidence['completed']=True
        finally:
            try:
                if census_observer:census_observer.close()
            finally:
                if memory_sampler:
                    memory=memory_sampler.stop()
                    (root/'research'/f'{prefix}-{args.renderer}-{args.side}-memory.json').write_text(json.dumps(memory,indent=2),encoding='utf-8')
                if hover_session:hover_session.detach()
                for capture_helper in captures:capture_helper.close()
                if handle:k.CloseHandle(handle)
                evidence.setdefault('owned_job_cleanup',job.finish(grace=0))
finally:
    failure=sys.exc_info()[1]
    if failure and not (evidence.get('diagnostic_completed') and isinstance(failure,SystemExit) and failure.code==2):
        evidence['error']=repr(failure)
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
    (root/'research'/f'{prefix}-{args.renderer}-{args.side}-observed.json').write_text(json.dumps(evidence,indent=2))
    if args.allocation_census:faulthandler.cancel_dump_traceback_later()
print('Tabs passed:',args.renderer,args.side,len(evidence['checks']),'checks')
