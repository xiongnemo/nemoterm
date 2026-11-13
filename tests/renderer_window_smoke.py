"""Owned GDI/OpenGL/DirectX windows: pixel parity, retained repaint, resize and sync.

Hardware is optional on CI: absence must take the working GDI fallback path.
Use NEMOTERM_REQUIRE_OPENGL=1 for the hardware acceptance run.
"""
from native_test_utils import *
from gpu_capture import OwnedGPUCapture
import uuid
import winreg
import atexit
import frida

exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
u.GetPropW.argtypes=[w.HWND,w.LPCWSTR];u.GetPropW.restype=w.HANDLE
font=os.environ.get('NEMOTERM_TEST_FONT','Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light')
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),font=font,modes=[],completed=False)
atexit.register(lambda:(root/'research/renderer-observed.json').write_text(json.dumps(evidence,indent=2)))
references={}
order=tuple(map(int,os.environ.get('NEMOTERM_TEST_RENDERER_ORDER','0,1,2').split(',')))
assert order and order[0]==0 and all(v in (0,1,2) for v in order)
diagnostic='NEMOTERM_TEST_RENDERER_ORDER' in os.environ
parity_failures=[]
with tempfile.TemporaryDirectory(prefix='nemoterm-renderer-') as tmp:
    for iteration,requested in enumerate(order):
        profile='renderer-test-'+uuid.uuid4().hex
        path='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,path) as key:
            for name,value in dict(NemoRenderer=requested,WarnOnClose=0).items():
                winreg.SetValueEx(key,name,0,winreg.REG_DWORD,value)
        report,control=(Path(tmp)/(str(requested)+n) for n in ('report','control'))
        label=f'{iteration}-{requested}' if diagnostic else str(requested)
        trace=root/'research'/f'renderer-{label}-clusters.txt'
        child_env=dict(os.environ,NEMOTERM_CONPTY='bundled')
        if os.environ.get('CI')=='true' or os.environ.get('NEMOTERM_TEST_CLUSTER_TRACE')=='1':
            trace.write_text('')
            child_env['NEMOTERM_CLUSTER_TRACE']=str(trace)
        process=subprocess.Popen([str(exe),'-load',profile,'--cols','80','--rows','24',
            '--font',font,'-e',sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control)],
            env=child_env,creationflags=subprocess.CREATE_NO_WINDOW)
        gl_capture = focus_session = None
        try:
            hwnd=wait_for(lambda:find_window(process.pid));wait_for(lambda:read_snapshot(report))
            active=int(u.GetPropW(hwnd,'NemotermRenderer') or 0)
            assert active in (1,2,3),(requested,active)
            if requested==0:assert active==1
            if requested==1 and os.environ.get('NEMOTERM_REQUIRE_OPENGL')=='1':assert active==2,'OpenGL fell back'
            if requested==2 and os.environ.get('NEMOTERM_REQUIRE_DIRECTX')=='1':assert active==3,'DirectX fell back'
            mode=dict(iteration=iteration,requested=requested,active={1:'GDI',2:'OpenGL',3:'DirectX'}[active],checks=[])
            evidence['modes'].append(mode)
            handle=k.OpenProcess(0x410,False,process.pid)
            try:mode['memory_before_instrumentation']=memory_sample(handle)
            finally:k.CloseHandle(handle)
            # A synthetic WM_KILLFOCUS alone is undone by the main loop's
            # real GetForegroundWindow check. Pin focus only inside this owned
            # process so GDI and GPU samples see the same cursor state.
            focus_session=frida.attach(process.pid)
            focus_script=focus_session.create_script((root/'tests/query_focus_probe.js').read_text())
            focus_errors=[]
            focus_script.on('message',lambda message,data:focus_errors.append(message) if message.get('type')=='error' else None)
            focus_script.load();focused=False
            focus_script.exports_sync.set_focus(hex(hwnd),focused)
            if active in (2,3):gl_capture=OwnedGPUCapture(process.pid,hwnd)
            mode['capture_method']='owned-process-retained-frame' if gl_capture else 'PrintWindow explicit client render'
            mode['memory_instrumented']=True
            mode['focus_model']='owned-process active and inactive states'
            def captured(name=None):
                # PW_RENDERFULLCONTENT may read an older DWM redirection
                # surface during resize. PW_CLIENTONLY requests our explicit
                # WM_PRINTCLIENT render, which also handles frozen GDI output.
                return gl_capture.capture(name,True) if gl_capture else capture(hwnd,name,True,print_flags=1)
            def render(name,sequence):
                write_snapshot(control,dict(phase=name,sequence=sequence+'\x1b[5n'))
                wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('phase')==name and bytes.fromhex(v.get('hex','')).endswith(b'\x1b[0n'))
                # The DSR acknowledges parsing. This synchronous owned-window
                # focus update also completes pending painting before capture.
                # Synchronized-output mode must still preserve its frozen frame.
                focus_script.exports_sync.set_focus(hex(hwnd),focused)
            def compare(name):
                pixels=captured(f'renderer-{label}-{name}.png')
                if not iteration:references[name]=pixels
                else:
                    expected=references[name]
                    mismatch=sum(a!=b for a,b in zip(pixels,expected))
                    # Windows ClearType on a memory DC can round a channel by
                    # up to two compared with the display DC, especially fallback
                    # glyphs. Geometry, solid colours and retained repaints
                    # remain strict; do not mask shifts or missing glyphs.
                    error=max(abs(a-b) for a,b in zip(pixels,expected))
                    mode['checks'].append(dict(scene=name,changed_channels=mismatch,max_channel_error=error))
                    passed=len(pixels)==len(expected) and error<=2 and mismatch<=len(pixels)//1000
                    if not passed:
                        parity_failures.append(dict(iteration=iteration,requested=requested,scene=name,changed_channels=mismatch,max_channel_error=error))
                    if not diagnostic:assert passed,parity_failures[-1:]
                if not iteration:mode['checks'].append(dict(scene=name))
                return pixels
            text=('\x1b[?25l\x1b[0m\x1b[2J\x1b[HASCII abc XYZ 0123\r\n'
                  '中文 e\u0301 A\u0308 \U0001f680 \ue0b0\r\n'
                  '\x1b[1;3;4:3;58:2::255:80:0mBold italic curly\x1b[0m\r\n'
                  '\x1b[7;9mReverse strike\x1b[0m\r\n'
                  '\x1b[38;2;90;180;220;48;2;32;40;48mTruecolour\x1b[0m\r\n'
                  '\x1b#6Double width\r\n\x1b#3Double height\r\n\x1b#4Double height\r\n')
            text+=('Repeated: '+('e\u0301 A\u0308 ')*6+'\r\n'+
                   '\x1b[?2027h'+('\U0001f469\u200d\U0001f4bb ')*8+'\x1b[?2027l\r\n'+
                   'abc \u05d0\u05d1\u05d2 123\r\n')
            for style in range(1,6):
                text+=(' '*style+f'\x1b[4:{style};58:2::255:80:0m'+
                       ('e\u0301 A\u0308 ')*5+'\x1b[0m\r\n')
            render('text',text);base=compare('text')
            # An expose must preserve both unchanged glyphs and the cached frame.
            u.RedrawWindow(hwnd,None,None,0x185);time.sleep(.1)
            assert captured(f'renderer-{requested}-expose.png')==base
            render('sixel',scene('SIXEL GPU composition','100;25;0'));base=compare('sixel')
            render('sync','\x1b[?2026h\x1b[Hhidden during synchronized update')
            u.RedrawWindow(hwnd,None,None,0x185)
            frozen=captured(f'renderer-{requested}-sync-frozen.png')
            if active==1:
                # GDI snapshots rerasterize into bounded memory-DC bands.
                # Consolas fallback/combining glyphs can round a few ClearType
                # channels by <=2. Limit that tolerance to the two text rows;
                # Sixel and every other pixel must remain byte-exact. Retained
                # GPU frames below have no such rerasterization allowance.
                client=w.RECT();assert u.GetClientRect(hwnd,c.byref(client))
                text_end=client.right*(1+2*((client.bottom-2)//24))*3
                changed=sum(a!=b for a,b in zip(frozen,base))
                error=max(abs(a-b) for a,b in zip(frozen,base))
                mode['gdi_snapshot_rounding']=dict(changed_channels=changed,max_channel_error=error)
                assert len(frozen)==len(base) and changed<=len(base)//1000 and error<=2
                assert frozen[text_end:]==base[text_end:]
            else:assert frozen==base
            render('sync-end','\x1b[?2026l');compare('sync-end')
            outer,client=w.RECT(),w.RECT()
            u.GetWindowRect(hwnd,c.byref(outer));u.GetClientRect(hwnd,c.byref(client))
            cw,ch=(client.right-2)//80,(client.bottom-2)//24
            u.MoveWindow(hwnd,outer.left,outer.top,outer.right-outer.left+10*cw,
                         outer.bottom-outer.top+4*ch,True)
            wait_for(lambda:(value:=read_snapshot(report)).get('columns')==90 and value.get('rows')==28)
            focus_script.exports_sync.set_focus(hex(hwnd),focused)
            compare('resize')
            # Palette changes must invalidate old cached run colours.
            render('palette','\x1b]10;#00ff80\x07\x1b]11;#101820\x07'+text)
            compare('palette')
            for focused in (True,False):
                for shape in (2,4,6):
                    name='cursor-'+('active-' if focused else 'inactive-')+str(shape)
                    render(name,'\x1b[?12l\x1b['+str(shape)+' q\x1b[?25h\x1b[2;4H')
                    compare(name)
            mode['focus_observations']=focus_script.exports_sync.stats()
            assert not focus_errors,focus_errors
            assert int(u.GetPropW(hwnd,'NemotermRenderer'))==active,'Renderer failed during drawing'
            handle=k.OpenProcess(0x410,False,process.pid)
            try:mode['memory']=memory_sample(handle)
            finally:k.CloseHandle(handle)
        finally:
            if gl_capture:gl_capture.close()
            if focus_session:focus_session.detach()
            write_snapshot(control,dict(stop=True))
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,path)
evidence['parity_failures']=parity_failures
evidence['completed']=not parity_failures
assert not parity_failures,parity_failures
print('GDI/OpenGL/DirectX pixel parity, text, Sixel, resize, expose and synchronized update passed:',[(v['active'],v['memory']) for v in evidence['modes']])
