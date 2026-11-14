"""Owned-window zoom, application mouse precedence, pixels and GDI lifetimes."""
import frida
import re
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, read_snapshot, write_snapshot, wait_for, wait_snapshot,
    find_window, terminal_host)
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile
from automation_capture import OwnedAutomationCapture

exe = Path(os.environ.get('NEMOTERM_TEST_EXE', root/'dist/nemoterm.exe')).resolve()
font = os.environ.get('NEMOTERM_TEST_FONT', 'Consolas' if os.environ.get('CI') == 'true'
                      else 'SarasaTermSC Nerd Font Light')
u.GetWindowRect.argtypes = [w.HWND,c.POINTER(w.RECT)]
u.GetClientRect.argtypes = [w.HWND,c.POINTER(w.RECT)]
u.ClientToScreen.argtypes = [w.HWND,c.POINTER(w.POINT)]
u.GetGuiResources.argtypes, u.GetGuiResources.restype = [w.HANDLE,w.DWORD],w.DWORD
u.GetPropW.argtypes, u.GetPropW.restype = [w.HWND,w.LPCWSTR],w.HANDLE
evidence = dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                font=font, memory_acceptance=False, input_method='owned UI thread', modes=[])
marker = b'\x1b[0n'
scene = ('\x1b[?25l\x1b[0m\x1b]10;#ffffff\x07\x1b]11;#000000\x07\x1b[2J'
         '\x1b[H\x1b[48;2;17;201;83m  \x1b[0m\x1b[2;2HM')

try:
    for renderer,zoom_modifier in ((0,2),(1,2),(2,2),(0,0)):
        mode = dict(requested_renderer=renderer, zoom_modifier=zoom_modifier, checks=[])
        evidence['modes'].append(mode)
        profile = dict(NemoRenderer=renderer, NemoTabs=int(renderer!=0), WarnOnClose=0,
            TrueColour=1, FontHeight=12, LockSize=0, NemoZoomModifiers=zoom_modifier,
            NemoZoomInBinding=0x37a, NemoZoomOutBinding=0x37b, NemoZoomResetBinding=0x379)
        with saved_profile(profile) as args, tempfile.TemporaryDirectory(prefix='nemo-zoom-') as tmp, OwnedJob() as job:
            report,control = Path(tmp)/'report.json',Path(tmp)/'control.json'
            process = job.spawn([str(exe),'--automation',*args,'--cols','80','--rows','24',
                '--font',font,'-e',sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control),'180'],
                env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1',
                         NEMOTERM_TEST_UTF8_INPUT='1'),creationflags=subprocess.CREATE_NO_WINDOW)
            handle = k.OpenProcess(0x410,False,process.pid)
            session = capture = None
            serial = 0
            request = {}
            try:
                hwnd = wait_for(lambda:find_window(process.pid))
                def current():
                    assert process.poll() is None
                    value = read_snapshot(report)
                    assert not value.get('error'),value
                    return value
                wait_for(current)
                mode['actual_renderer'] = int(u.GetPropW(hwnd,'NemotermRenderer') or 0)
                assert mode['actual_renderer'] in (1,2,3)
                capture = OwnedAutomationCapture(process.pid,hwnd)
                session = frida.attach(process.pid)
                script = session.create_script((root/'tests/agent_key_probe.js').read_text())
                script.load(); script.exports_sync.isolate_mouse(hex(hwnd))
                def action(**op):
                    global serial
                    serial += 1
                    script.exports_sync.key(dict(id=serial,**op))
                    assert u.PostMessageW(hwnd,0x8322,0,0)
                    assert wait_for(lambda:script.exports_sync.result()) == dict(id=serial)
                def phase(name,sequence):
                    global serial,request
                    serial += 1
                    request = dict(phase=f'{serial}-{name}',sequence=sequence+'\x1b[5n',preserve_mouse=True)
                    write_snapshot(control,request)
                    value = wait_snapshot(current,lambda v:v.get('phase')==request['phase'] and
                                          bytes.fromhex(v.get('hex','')).endswith(marker))
                    return bytes.fromhex(value['hex'])[:-len(marker)]
                def barrier(expected):
                    global serial
                    serial += 1
                    write_snapshot(control,dict(request,input_barrier=str(serial)))
                    value = wait_snapshot(current,lambda v:v.get('input_barrier')==str(serial))
                    assert bytes.fromhex(value['hex']) == expected+marker, value
                def outer():
                    r=w.RECT(); assert u.GetWindowRect(terminal_host(hwnd),c.byref(r))
                    return [r.left,r.top,r.right,r.bottom]
                def metrics(name):
                    raw = phase(name,scene+'\x1b[16t\x1b[18t')
                    match = re.fullmatch(rb'\x1b\[6;(\d+);(\d+)t\x1b\[8;(\d+);(\d+)t',raw)
                    assert match,(name,raw)
                    ch,cw,rows,cols = map(int,match.groups())
                    def pixels_ready():
                        rgb = capture.capture(return_pixels=True)
                        green = sum(rgb[i:i+3]==b'\x11\xc9\x53' for i in range(0,len(rgb),3))
                        return rgb if green == 2*cw*ch else None
                    rgb = wait_for(pixels_ready)
                    r=w.RECT(); u.GetClientRect(hwnd,c.byref(r))
                    white=[i//3 for i in range(0,len(rgb),3) if min(rgb[i:i+3])>160]
                    assert white
                    xs,ys=[i%r.right for i in white],[i//r.right for i in white]
                    item=dict(name=name,cell=[cw,ch],grid=[cols,rows],outer=outer(),
                              glyph=[max(xs)-min(xs)+1,max(ys)-min(ys)+1])
                    mode['checks'].append(item)
                    return item
                def wheel(delta,keys):
                    r=w.RECT();u.GetClientRect(hwnd,c.byref(r))
                    point=w.POINT(r.right//2,r.bottom//2);u.ClientToScreen(hwnd,c.byref(point))
                    mods=([17,162] if keys&8 else [])+([16,160] if keys&4 else [])
                    action(modifiers=mods,mouse=[dict(message=0x20a,
                        keys=((delta&65535)<<16)|keys,point=(point.x&65535)|((point.y&65535)<<16))])
                initial = metrics('initial')
                if not zoom_modifier:
                    phase('disabled-wheel','');wheel(120,8);barrier(marker)
                    assert metrics('disabled-wheel-unchanged')['cell']==initial['cell']
                    phase('disabled-app-mouse','\x1b[?1000;1006h');wheel(120,8)
                    value=wait_snapshot(current,lambda v:re.search(rb'\x1b\[<80;\d+;\d+M$',bytes.fromhex(v.get('hex',''))))
                    barrier(bytes.fromhex(value['hex']))
                    assert metrics('disabled-app-unchanged')['cell']==initial['cell']
                    session.detach();session=None
                    write_snapshot(control,dict(stop=True))
                    assert process.wait(timeout=10)==0
                    mode['cleanup']=job.finish(grace=5)
                    assert not mode['cleanup']['terminated_remaining']
                    mode['completed']=True
                    continue
                phase('half-wheel','');wheel(60,8);barrier(marker)
                assert metrics('half-unchanged')['cell']==initial['cell']
                phase('second-half','');wheel(60,8);barrier(marker)
                larger=metrics('larger')
                assert larger['cell'][1]>initial['cell'][1] and larger['glyph'][1]>initial['glyph'][1]
                assert larger['outer']==initial['outer'] and larger['grid'][1]<initial['grid'][1]
                u.SendMessageW(hwnd,0x111,0x0960,0)
                assert metrics('menu-reset')['cell']==initial['cell']
                phase('app-mouse','\x1b[?1000;1006h');wheel(120,8)
                value=wait_snapshot(current,lambda v:re.search(rb'\x1b\[<80;\d+;\d+M$',bytes.fromhex(v.get('hex',''))))
                barrier(bytes.fromhex(value['hex']))
                assert metrics('app-ctrl-passed')['cell']==initial['cell']
                phase('forced-local','');wheel(120,12);barrier(marker)
                assert metrics('forced-local-larger')['cell'][1]>initial['cell'][1]
                phase('keys','\x1b[?1000l\x1b[>3u')
                action(key=0x79,modifiers=[16,17,160,162]);barrier(marker)
                assert metrics('bound-reset')['cell']==initial['cell']
                phase('bound-in','');action(key=0x7a,modifiers=[16,17,160,162]);barrier(marker)
                assert metrics('bound-increased')['cell'][1]>initial['cell'][1]
                phase('bound-out','');action(key=0x7b,modifiers=[16,17,160,162]);barrier(marker)
                assert metrics('bound-decreased')['cell']==initial['cell']
                gdi_before=u.GetGuiResources(handle,0)
                for cycle in range(6):
                    u.SendMessageW(hwnd,0x111,0x0940,0)
                    metrics('cycle-up-'+str(cycle))
                    u.SendMessageW(hwnd,0x111,0x0960,0)
                    assert metrics('cycle-reset-'+str(cycle))['cell']==initial['cell']
                mode['gdi_resources']=[gdi_before,u.GetGuiResources(handle,0)]
                assert mode['gdi_resources'][1] <= gdi_before,mode['gdi_resources']
                session.detach();session=None
                write_snapshot(control,dict(stop=True))
                assert process.wait(timeout=10)==0
                mode['cleanup']=job.finish(grace=5)
                assert not mode['cleanup']['terminated_remaining']
                mode['completed']=True
            finally:
                if session: session.detach()
                if capture: capture.close()
                if handle:k.CloseHandle(handle)
                mode.setdefault('cleanup',job.finish(grace=0))
finally:
    (root/'research/font-zoom-observed.json').write_text(json.dumps(evidence,indent=2))
print('Font zoom passed for actual renderers:',[m['actual_renderer'] for m in evidence['modes']])
