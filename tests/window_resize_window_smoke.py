"""Application resize requests through real ConPTY, with Win32 size evidence."""
from native_test_utils import *
from owned_job import OwnedJob
from gpu_capture import OwnedGPUCapture
import argparse
import re
import uuid
import winreg

parser=argparse.ArgumentParser()
parser.add_argument('--renderer',type=int,choices=(0,1,2))
parser.add_argument('--tabs',action='store_true')
parser.add_argument('--tab-side',choices=('top','bottom','left','right'),default='top')
args=parser.parse_args()
exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
font=os.environ.get('NEMOTERM_TEST_FONT','Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light')
u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
u.GetWindowRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
u.GetClientRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
u.MonitorFromWindow.argtypes,u.MonitorFromWindow.restype=[w.HWND,w.DWORD],w.HANDLE
u.GetMonitorInfoW.argtypes=[w.HANDLE,c.c_void_p]
u.ShowWindow.argtypes=[w.HWND,c.c_int]
u.IsIconic.argtypes=[w.HWND]
u.IsZoomed.argtypes=[w.HWND]
class MonitorInfo(c.Structure):
    _fields_=[('size',w.DWORD),('monitor',w.RECT),('work',w.RECT),('flags',w.DWORD)]

CSI='\x1b['
queries=CSI+'14t'+CSI+'14;2t'+CSI+'16t'+CSI+'18t'+CSI+'5n'
evidence=dict(tab_host=args.tabs,tab_side=args.tab_side,executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    font=font,reference_run=43271622637,modes=[],runtime_files={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
    for p in (exe.parent/'OpenConsole.exe',exe.parent/'conpty.dll') if p.exists()})
profiles=[('normal',0,False,r) for r in ((args.renderer,) if args.renderer is not None else (0,1,2))]
profiles += [('remote-denied',0,True,0),('locked-window',1,False,0),('font-resize',2,False,0)]

try:
    for name,lock,denied,renderer in profiles:
        profile='window-resize-'+uuid.uuid4().hex
        keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
        mode=dict(policy=name,requested_renderer=renderer,checks=[]);evidence['modes'].append(mode)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:
            for option,value in dict(LockSize=lock,NoRemoteResize=int(denied),WarnOnClose=0,NemoRenderer=renderer).items():
                winreg.SetValueEx(key,option,0,winreg.REG_DWORD,value)
        try:
            with tempfile.TemporaryDirectory(prefix='nemoterm-window-resize-') as tmp,OwnedJob() as job:
                report,control=Path(tmp)/'report',Path(tmp)/'control'
                process=job.spawn([str(exe)]+(['--tabs','--tab-side',args.tab_side] if args.tabs else [])+['-load',profile,'--cols','83','--rows','27',
                    '--font',font,'--font-size','12','-e',sys.executable,
                    str(root/'tests/mouse_fixture.py'),str(report),str(control)],
                    env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1'),
                    creationflags=subprocess.CREATE_NO_WINDOW)
                handle=k.OpenProcess(0x410,False,process.pid)
                gl=None
                try:
                    hwnd=wait_for(lambda:find_window(process.pid));wait_for(lambda:read_snapshot(report))
                    active=int(u.GetPropW(hwnd,'NemotermRenderer') or 0)
                    assert active in (1,2,3)
                    if not renderer:assert active==1
                    if renderer==1 and os.environ.get('NEMOTERM_REQUIRE_OPENGL')=='1':assert active==2
                    if renderer==2 and os.environ.get('NEMOTERM_REQUIRE_DIRECTX')=='1':assert active==3
                    mode['active_renderer']=active
                    mode['memory_before_instrumentation']=memory_sample(handle)
                    # Sample all resize phases before loading capture tooling.
                    # Only the final retained-pixel assertion needs injection.
                    mode['memory_instrumented']=False
                    def rectangles():
                        outer,client=w.RECT(),w.RECT()
                        assert u.GetWindowRect(terminal_host(hwnd),c.byref(outer));assert u.GetClientRect(hwnd,c.byref(client))
                        return [outer.right-outer.left,outer.bottom-outer.top],[client.right,client.bottom]
                    outer,initial=rectangles()
                    frame=[outer[i]-initial[i] for i in (0,1)]
                    monitor=MonitorInfo();monitor.size=c.sizeof(monitor)
                    assert u.GetMonitorInfoW(u.MonitorFromWindow(hwnd,2),c.byref(monitor))
                    screen=[monitor.monitor.right-monitor.monitor.left,monitor.monitor.bottom-monitor.monitor.top]
                    limit=[screen[i]-frame[i] for i in (0,1)]
                    mode.update(initial_client=initial,frame=frame,screen=screen)
                    def phase(label,sequence='',client=None,grid=None,iconic=False):
                        write_snapshot(control,dict(phase=label,sequence=sequence+queries))
                        value=wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('phase')==label and
                            bytes.fromhex(v.get('hex','')).endswith(b'\x1b[0n'))
                        raw=bytes.fromhex(value['hex']).decode('ascii')
                        replies=[list(map(int,x.split(';'))) for x in re.findall('\x1b\\[([0-9;]+)t',raw)]
                        assert len(replies)==4,(label,raw)
                        # ConPTY's size-control pipe and input pipe are separate.
                        # After frontend rejection, wait for its authoritative
                        # size to reach the child, not just the DSR input reply.
                        value=wait_snapshot(lambda:read_snapshot(report),lambda v:
                            v.get('phase')==label and [v.get('rows'),v.get('columns')]==replies[3][1:])
                        outer,actual=rectangles()
                        cw,ch=replies[2][2],replies[2][1]
                        assert replies[0]==[4,value['rows']*ch,value['columns']*cw],(label,replies,value)
                        assert replies[1]==[4,outer[1],outer[0]],(label,replies,outer)
                        assert replies[3]==[8,value['rows'],value['columns']],(label,replies,value)
                        if client is not None:assert actual==client,(label,actual,client)
                        if grid is not None:assert [value['columns'],value['rows']]==grid,(label,value,grid)
                        assert bool(u.IsIconic(terminal_host(hwnd)))==iconic,(label,'iconic state changed')
                        assert int(u.GetPropW(hwnd,'NemotermRenderer') or 0)==active,(label,'renderer changed')
                        mode['checks'].append(dict(name=label,client=actual,outer=outer,replies=replies,
                            child_grid=[value['columns'],value['rows']],memory=memory_sample(handle)))
                        return cw,ch
                    cw,ch=phase('initial',grid=[83,27])
                    base=[2+83*cw,2+27*ch]
                    assert initial==base,(initial,base)
                    if name in ('remote-denied','locked-window'):
                        for index,command in enumerate(('8;30;90t','4;213;489t','8;0;0t','48t')):
                            phase('denied-'+str(index),CSI+command,client=initial,grid=[83,27])
                    elif name=='font-resize':
                        phase('font-grid',CSI+'8;20;60t',client=initial,grid=[60,20])
                        phase('font-pixels',CSI+'4;503;703t',client=[703,503],grid=[60,20])
                        phase('font-partial-grid',CSI+'8;;70t',client=[703,503],grid=[70,20])
                        u.ShowWindow(terminal_host(hwnd),7);wait_for(lambda:u.IsIconic(terminal_host(hwnd)))
                        phase('font-minimized-pixels',CSI+'4;563;733t',grid=[70,20],iconic=True)
                        u.ShowWindow(terminal_host(hwnd),9);wait_for(lambda:not u.IsIconic(terminal_host(hwnd)))
                        phase('font-restored-pixels',client=[733,563],grid=[70,20])
                    else:
                        cases=[
                            ('chars','8;30;90t',[2+90*cw,2+30*ch],[90,30]),
                            ('row-only','8;30t',[base[0],2+30*ch],[83,30]),
                            ('column-only','8;;90t',[2+90*cw,base[1]],[90,27]),
                            ('omitted','8t',base,[83,27]),
                            ('empty','8;;t',base,[83,27]),
                            ('zero-row','8;0;83t',[base[0],limit[1]],None),
                            ('zero-column','8;27;0t',[limit[0],base[1]],None),
                            ('zero-both','8;0;0t',limit,None),
                            ('pixels','4;213;489t',[489,213],None),
                            ('pixel-row','4;213;t',[base[0],213],None),
                            ('pixel-column','4;;489t',[489,base[1]],None),
                            ('pixel-omitted','4t',base,[83,27]),
                            ('pixel-zero-row','4;0;489t',[489,limit[1]],None),
                            ('pixel-zero-column','4;213;0t',[limit[0],213],None),
                            ('pixel-zero-both','4;0;0t',limit,None),
                            ('extra-parameters','8;30;90;123t',[2+90*cw,2+30*ch],[90,30]),
                            ('colon-rejected','8;30:1;90t',base,[83,27]),
                            ('pixel-colon-rejected','4;213:1;489t',base,[83,27]),
                            ('lines-31','31t',[base[0],2+31*ch],[83,31]),
                            ('lines-extra','31;99t',[base[0],2+31*ch],[83,31]),
                            ('huge-chars-rejected','8;65536;90t',base,[83,27]),
                            ('huge-pixels-limited','4;65536;489t',[489,limit[1]],None),
                            ('saturated-pixels','4;999999999999999999;489t',[489,limit[1]],None),
                            ('default-op','t',base,[83,27]),
                            ('zero-op','0t',base,[83,27]),
                            ('pixels-keep-current','4;213;489t'+CSI+'4t',[489,213],None),
                            ('chars-snap-current','4;213;489t'+CSI+'8t',
                             [2+((489-2)//cw)*cw,2+((213-2)//ch)*ch],None),
                            ('cancelled','4;213;489\x18X',base,[83,27]),
                        ]
                        for label,command,size,grid in cases:
                            phase(label,CSI+'8;27;83t'+CSI+command,client=size,grid=grid)
                        # The Win32 minimum caption size may exceed one cell.
                        # Native replies and child dimensions must agree even
                        # when the OS imposes that extra minimum.
                        for label,command in (('one-cell','8;1;1t'),
                                              ('one-pixel','4;1;1t'),
                                              ('sub-cell-pixels','4;7;7t')):
                            phase(label,CSI+'8;27;83t'+CSI+command)
                            actual=rectangles()[1]
                            minimum=[max(cw+2,u.GetSystemMetrics(34)-frame[0]),
                                     max(ch+2,u.GetSystemMetrics(35)-frame[1])]
                            assert actual==minimum,(label,actual,minimum)
                            mode['checks'][-1]['requested_client_minimum']=[cw+2,ch+2]
                        # Sequential requests in a single write must not overtake
                        # the resize completion or lose intervening output.
                        phase('ordered-resizes',CSI+'8;20;60t'+CSI+'2JORDERED'+CSI+'8;30;90t',
                              client=[2+90*cw,2+30*ch],grid=[90,30])
                        phase('sync-resize',CSI+'?2026h'+CSI+'8;27;83t',client=base,grid=[83,27])
                        phase('alternate-resize',CSI+'?1049h'+CSI+'8;22;72t',
                              client=[2+72*cw,2+22*ch],grid=[72,22])
                        phase('main-return',CSI+'?1049l',client=[2+72*cw,2+22*ch],grid=[72,22])
                        phase('pre-maximize',CSI+'8;27;83t',client=base,grid=[83,27])
                        u.ShowWindow(terminal_host(hwnd),3);wait_for(lambda:u.IsZoomed(terminal_host(hwnd)))
                        phase('maximized')
                        maximized_client=rectangles()[1]
                        phase('maximized-request-denied',CSI+'8;20;60t',client=maximized_client)
                        u.ShowWindow(terminal_host(hwnd),9);wait_for(lambda:not u.IsZoomed(terminal_host(hwnd)))
                        phase('unmaximized',client=base,grid=[83,27])
                        u.ShowWindow(terminal_host(hwnd),7);wait_for(lambda:u.IsIconic(terminal_host(hwnd)))
                        drawing=CSI+'?25l'+CSI+'2J'+CSI+'1;1H'+CSI+'48;2;19;193;101m  '+CSI+'0m'
                        phase('minimized-request',CSI+'8;25;81t'+drawing,grid=[81,25],iconic=True)
                        u.ShowWindow(terminal_host(hwnd),9);wait_for(lambda:not u.IsIconic(terminal_host(hwnd)))
                        phase('restored-request',client=[2+81*cw,2+25*ch],grid=[81,25])
                        if active in (2,3):gl=OwnedGPUCapture(process.pid,hwnd)
                        mode['capture_instrumented']=bool(gl)
                        def captured():
                            return gl.capture(return_pixels=True) if gl else capture(hwnd,return_pixels=True)
                        colour=bytes((19,193,101))
                        wait_for(lambda:captured().count(colour)>=2*cw*ch)
                        if gl:gl.capture(f'window-resize-gpu-{active}.png')
                        else:capture(hwnd,'window-resize-gdi.png')
                        mode['minimized_output_preserved']=True
                    if active==1:
                        assert max(v['memory']['private_ws'] for v in mode['checks'])<20_000_000
                    write_snapshot(control,dict(stop=True));assert process.wait(timeout=10)==0
                finally:
                    if gl:gl.close()
                    job.finish(grace=0);process.wait(timeout=5);k.CloseHandle(handle)
        finally:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
    evidence['completed']=True
finally:
    if sys.exc_info()[0]:evidence['error']=repr(sys.exc_info()[1])
    (root/'research'/('tabs-window-resize-observed.json' if args.tabs else 'window-resize-observed.json')).write_text(json.dumps(evidence,indent=2))
print('Native window resize passed:',[(m['policy'],m['active_renderer'],len(m['checks'])) for m in evidence['modes']])
