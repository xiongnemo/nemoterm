"""Actual Windows scaling of an exact product image; hosted CI desktop only.

The native helper may request a system change, but only GetDpiForWindow on the
uninstrumented product can satisfy a real-DPI case. No API results are hooked.
"""
import ctypes as c
import os
if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
    raise SystemExit('Run this test on a disposable GitHub-hosted Windows runner')
c.windll.user32.SetProcessDpiAwarenessContext(c.c_void_p(-4))
from native_test_utils import *
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile
import argparse,re,traceback
sys.path.insert(0,str(root/'tools'))
import nemoterm_debug as api

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--display-helper',required=True,type=Path)
parser.add_argument('--renderer',choices=('gdi','opengl','directx'),default='gdi')
parser.add_argument('--ui-language',choices=('en','zh-CN'),default='en')
parser.add_argument('--settings-page',choices=('rendering',))
args=parser.parse_args()
helper_path=args.display_helper.resolve()
exe=Path(os.environ['NEMOTERM_TEST_EXE']).resolve()
u.GetDpiForWindow.argtypes=[w.HWND];u.GetDpiForWindow.restype=w.UINT
u.GetWindowDpiAwarenessContext.argtypes=[w.HWND];u.GetWindowDpiAwarenessContext.restype=w.HANDLE
u.AreDpiAwarenessContextsEqual.argtypes=[w.HANDLE,w.HANDLE]
u.GetWindowRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
u.GetClassNameW.argtypes=[w.HWND,w.LPWSTR,c.c_int]
u.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]
u.IsWindowEnabled.argtypes=[w.HWND]
u.GetPropW.argtypes=[w.HWND,w.LPCWSTR];u.GetPropW.restype=w.HANDLE
ENUM=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
u.EnumWindows.argtypes=[ENUM,w.LPARAM]
renderer_number={'gdi':0,'opengl':1,'directx':2}[args.renderer]
evidence=dict(completed=False,method='real system display scale; no injected DPI',renderer=args.renderer,
    ui_language=args.ui_language,settings_page=args.settings_page,
    executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),fixture_commit=os.environ.get('GITHUB_SHA'),
    product_commit=os.environ.get('NEMOTERM_DPI_PRODUCT_COMMIT'),product_run=os.environ.get('NEMOTERM_DPI_PRODUCT_RUN'),
    cases=[],attempts=[],coverage_gaps=['Mixed-DPI multi-monitor moves are not exercised by this single-monitor fixture'],failures=[])
evidence_path=root/'research'/f'dpi-real-{args.renderer}-{args.ui_language}.json'

def save(): evidence_path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
def helper(*values):
    completed=subprocess.run([str(helper_path),*map(str,values)],capture_output=True,text=True,timeout=15,check=True)
    return json.loads(completed.stdout)
def primary(snapshot): return next(m for m in snapshot['monitors'] if m['primary'])
def change(percent):
    result=helper('--set-percent',percent);evidence['attempts'].append(result);save()
    deadline=time.monotonic()+5
    while True:
        observed=helper()
        if primary(observed)['dpi']==percent*96//100:return observed
        if time.monotonic()>=deadline:return None
        time.sleep(.15)
def dialog_window(pid):
    found=[]
    @ENUM
    def visit(hwnd,_):
        owner=w.DWORD();name=c.create_unicode_buffer(64)
        u.GetWindowThreadProcessId(hwnd,c.byref(owner));u.GetClassNameW(hwnd,name,len(name))
        if owner.value==pid and name.value=='PuTTYConfigBox':found.append(hwnd)
        return True
    u.EnumWindows(visit,0)
    return next(iter(found),None)
def inspect_settings(process,hwnd,dpi,prefix):
    evidence=dict(completed=False,expected_dpi=dpi,hwnd=hwnd,pages=[],ui_language=args.ui_language,client='native UIAutomation')
    try:
        pages=(args.settings_page,) if args.settings_page else ('profile','shell','keyboard','terminfo','extended','bell','bell-overload','bindings','font','font-access','rendering','translation','line-drawing','tabs','language')
        for page in pages:
            result=subprocess.run([str(helper_path.with_name('dpi-settings.exe')),str(process.pid),str(hwnd),str(dpi),page,args.ui_language],
                capture_output=True,text=True,timeout=20)
            (root/'research'/f'{prefix}-{page}.log').write_text(result.stdout+result.stderr,encoding='utf-8')
            if not result.stdout.strip():
                raise RuntimeError(f'{page} helper returned {result.returncode:#x} without JSON: {result.stderr}')
            observed=json.loads(result.stdout);evidence['pages'].append(observed)
            observed['screenshot']=f'{prefix}-{page}.png'
            try:
                capture(hwnd,observed['screenshot'])
            except Exception:
                observed['screenshot_error']=traceback.format_exc()
                observed['product_exit_code']=process.poll()
                observed['settings_window_alive']=bool(u.IsWindow(hwnd))
            assert result.returncode==0 and observed['completed'],observed
            assert 'screenshot_error' not in observed,observed
            if page=='rendering':
                caps=[c['rect'] for c in observed['controls'] if c['label'].startswith(('Continue unfinished','Move ReGIS'))]
                assert len(caps)==2 and caps[0][1]+caps[0][3]<caps[1][1],caps
        evidence['completed']=True
    finally:
        (root/'research'/f'{prefix}-settings.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        u.PostMessageW(hwnd,0x111,2,0)

initial=helper();evidence['initial_environment']=initial;save()
baseline_percent=primary(initial)['dpi']*100//96
initial_bounds=primary(initial)['bounds']
initial_size=[initial_bounds[2]-initial_bounds[0],initial_bounds[3]-initial_bounds[1]]
scene=('\x1b[2J\x1b[3J\x1b[H\x1b[2 q\x1b[?25h\x1b]12;#00ff00\x07\x1b]11;#000000\x07'
       '\x1b[3;3H\x1bP0;1q"1;1;24;12#1;2;100;0;0!24~-!24~\x1b\\'
       '\x1b[6;2HChinese: 中文  emoji: 🙂  combined: e\u0301\x1b[H')

def exercise(tabbed,start_percent,warm):
    kind='tabs' if tabbed else 'standalone'
    profile=dict(NemoTabs=int(tabbed),NemoRenderer=renderer_number,WarnOnClose=0,FontHeight=12,NemoWin32Input=0)
    with saved_profile(profile) as profile_args,tempfile.TemporaryDirectory(prefix='nemo-real-dpi-') as directory,OwnedJob() as job:
        report,control=Path(directory)/'report.json',Path(directory)/'control.json'
        process=job.spawn([str(exe),'--automation','--ui-language',args.ui_language,*profile_args,'--cols','40','--rows','12','--font','Consolas','-e',
            sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control),'600'],
            env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1'),creationflags=subprocess.CREATE_NO_WINDOW)
        case=dict(host=kind,start_percent=start_percent,transition=warm,completed=False,frames=[])
        evidence['cases'].append(case);save()
        try:
            hwnd=wait_for(lambda:find_window(process.pid));host=terminal_host(hwnd)
            host_class=c.create_unicode_buffer(64);u.GetClassNameW(host,host_class,len(host_class))
            case['actual_host_class']=host_class.value
            assert host_class.value==('NemotermHost' if tabbed else 'Nemoterm'),case
            case['active_renderer']=int(u.GetPropW(hwnd,'NemotermRenderer') or 0)
            wait_for(lambda:read_snapshot(report))
            assert u.GetDpiForWindow(host)==start_percent*96//100
            assert u.AreDpiAwarenessContextsEqual(u.GetWindowDpiAwarenessContext(host),c.c_void_p(-4)), 'Product is not PMv2 aware'
            assert case['active_renderer']==renderer_number+1,'Renderer fell back'
            instance=wait_for(lambda:next(iter(api.discover(process.pid)),None));endpoint=instance['endpoint'];sid=instance['sessions'][0]['id']
            base_cell=None;base_dpi=None
            for percent in (targets+[baseline_percent] if warm else [start_percent]):
                dpi=percent*96//100
                prefix=f'real-{args.renderer}-{args.ui_language}-{kind}-'+('warm' if warm else 'cold')+f'-{percent}-{len(case["frames"])}'
                # In warm cases the dialog already exists while Windows changes DPI.
                u.PostMessageW(hwnd,0x111,0x50,0)
                settings=wait_for(lambda:dialog_window(process.pid))
                if warm:
                    environment=change(percent)
                    if environment is None:
                        u.PostMessageW(settings,0x111,2,0)
                        raise AssertionError(('Advertised scale failed to take effect',percent))
                    wait_for(lambda:u.GetDpiForWindow(host)==dpi and u.GetDpiForWindow(settings)==dpi)
                assert u.GetDpiForWindow(host)==dpi and u.GetDpiForWindow(hwnd)==dpi
                frame=dict(requested_percent=percent,actual_host_dpi=u.GetDpiForWindow(host),
                    actual_content_dpi=u.GetDpiForWindow(hwnd),actual_dialog_dpi=u.GetDpiForWindow(settings),prefix=prefix)
                case['frames'].append(frame);save()
                inspect_settings(process,settings,dpi,prefix)
                wait_for(lambda:not u.IsWindow(settings) and u.IsWindowEnabled(host))
                write_snapshot(control,dict(phase=prefix,sequence=scene+'\x1b[16t\x1b[5n'))
                value=wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('phase')==prefix and v.get('hex','').endswith('1b5b306e'))
                cell=re.search(rb'\x1b\[6;(\d+);(\d+)t',bytes.fromhex(value['hex']))
                assert cell,value
                ch,cw=map(int,cell.groups());frame.update(cell_width=cw,cell_height=ch,cols=value['columns'],rows=value['rows'])
                if base_cell is None:base_cell=(cw,ch);base_dpi=dpi
                for actual,base in zip((cw,ch),base_cell):assert abs(actual-base*dpi/base_dpi)<=2,(frame,base_cell,base_dpi)
                def pixels_match():
                    r=w.RECT();u.GetClientRect(hwnd,c.byref(r));pixels=capture(hwnd,return_pixels=True)
                    green=[];red=set()
                    for i in range(0,len(pixels),3):
                        colour=pixels[i:i+3];point=(i//3%r.right,i//3//r.right)
                        if colour==b'\0\xff\0':green.append(point)
                        elif colour==b'\xff\0\0':red.add(point)
                    if not green:return None
                    xs,ys=zip(*green);x,y=min(xs),min(ys)
                    if max(xs)-x+1!=cw or max(ys)-y+1!=ch:return None
                    return [x,y] if red=={(x+2*cw+xx,y+2*ch+yy) for xx in range(24) for yy in range(12)} else None
                frame['cell_origin']=wait_for(pixels_match)
                frame['screenshot']=prefix+'-terminal.png';capture(hwnd,frame['screenshot'])
                # Input still reaches the same session after scaling and closing its dialog.
                api.request(endpoint,'input',sid,'DPI_OK')
                wait_for(lambda:'DPI_OK'.encode().hex() in read_snapshot(report).get('hex',''))
                save()
            case['completed']=True
        except Exception:
            case['error']=traceback.format_exc()
            case['product_exit_code']=process.poll()
            raise
        finally:
            settings=dialog_window(process.pid)
            if settings:u.PostMessageW(settings,0x111,2,0)
            write_snapshot(control,dict(stop=True))
            try:
                process.wait(timeout=10)
                assert process.returncode==0,process.returncode
            except Exception:
                case['completed']=False;raise
            finally:
                case['cleanup']=job.finish()
                if case['cleanup']['terminated_remaining']:case['completed']=False
                save()
                assert not case['cleanup']['terminated_remaining'],case['cleanup']

try:
    # A larger advertised mode can expose higher real scales on a virtual
    # display. Never force an unadvertised mode or install a display driver.
    modes=[m[:2] for m in primary(initial).get('display_modes',[]) if m[0]>=1024 and m[1]>=768]
    # Prefer logical desktop room in both axes. On this runner 1600x1200
    # gives more vertical room for 200% than 1920x1080. Query again below;
    # the selected resolution alone is not proof of any supported scale.
    best=max(modes,key=lambda m:(min(m[0]/800,m[1]/600),m[0]*m[1]),default=initial_size)
    if initial_size != best:
        evidence['resolution_preparation']=helper('--set-size',*best);save()
    prepared=helper();evidence['prepared_environment']=prepared
    source=next((s for s in prepared['sources'] if s['device']==primary(prepared)['device']),None)
    available=source['supported_percentages'] if source else []
    targets=[v for v in (100,125,150,175,200) if v in available or v==baseline_percent]
    evidence['coverage_gaps'] += [f'Real {v}% unsupported by this display driver' for v in (100,125,150,175,200) if v not in targets]
    save()
    for tabbed in (False,True):
        for percent in targets:
            try:
                if primary(helper())['dpi']!=percent*96//100 and change(percent) is None:
                    raise AssertionError(('Advertised scale unavailable',percent))
                exercise(tabbed,percent,False)
            except Exception:evidence['failures'].append(traceback.format_exc());save()
        # Compare fresh-process cell geometry across real system scales too.
        cold=[v for v in evidence['cases'] if v['host']==('tabs' if tabbed else 'standalone') and not v['transition'] and v['completed']]
        if cold:
            baseline=cold[0]['frames'][0]
            for case in cold[1:]:
                frame=case['frames'][0]
                for axis in ('cell_width','cell_height'):
                    if abs(frame[axis]-baseline[axis]*frame['actual_host_dpi']/baseline['actual_host_dpi'])>2:
                        case['completed']=False
                        case['error']=f'Cold-start {axis} did not scale: {baseline} -> {frame}'
                        evidence['failures'].append(case['error'])
        if len(targets)>1:
            try:
                assert change(baseline_percent)
                exercise(tabbed,baseline_percent,True)
            except Exception:evidence['failures'].append(traceback.format_exc());save()
    evidence['completed']=not evidence['failures'] and bool(evidence['cases'])
finally:
    if primary(helper())['dpi']!=baseline_percent*96//100:
        restored=change(baseline_percent)
        if restored is None:evidence['failures'].append('Display restoration failed');evidence['completed']=False
    bounds=primary(helper())['bounds']
    if [bounds[2]-bounds[0],bounds[3]-bounds[1]]!=initial_size:
        evidence['resolution_restoration']=helper('--set-size',*initial_size)
        bounds=primary(helper())['bounds']
        if [bounds[2]-bounds[0],bounds[3]-bounds[1]]!=initial_size:
            evidence['failures'].append('Resolution restoration failed');evidence['completed']=False
    evidence['final_environment']=helper();save()
print(json.dumps(evidence,indent=2))
if not evidence['completed']:raise SystemExit(1)
