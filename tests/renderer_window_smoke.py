"""Owned GDI/OpenGL windows: pixel parity, retained repaint, resize and sync.

Hardware is optional on CI: absence must take the working GDI fallback path.
Use NEMOTERM_REQUIRE_OPENGL=1 for the hardware acceptance run.
"""
from native_test_utils import *
import uuid
import winreg

exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
u.GetPropW.argtypes=[w.HWND,w.LPCWSTR];u.GetPropW.restype=w.HANDLE
font=os.environ.get('NEMOTERM_TEST_FONT','Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light')
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),font=font,modes=[])
references={}
with tempfile.TemporaryDirectory(prefix='nemoterm-renderer-') as tmp:
    for requested in (0,1):
        profile='renderer-test-'+uuid.uuid4().hex
        path='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,path) as key:
            for name,value in dict(NemoRenderer=requested,WarnOnClose=0).items():
                winreg.SetValueEx(key,name,0,winreg.REG_DWORD,value)
        report,control=(Path(tmp)/(str(requested)+n) for n in ('report','control'))
        process=subprocess.Popen([str(exe),'-load',profile,'--cols','80','--rows','24',
            '--font',font,'-e',sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control)],
            env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            hwnd=wait_for(lambda:find_window(process.pid));wait_for(lambda:read_snapshot(report))
            active=int(u.GetPropW(hwnd,'NemotermRenderer') or 0)
            assert active in (1,2),(requested,active)
            if requested==0:assert active==1
            if requested and os.environ.get('NEMOTERM_REQUIRE_OPENGL')=='1':assert active==2,'OpenGL fell back'
            mode=dict(requested=requested,active='OpenGL' if active==2 else 'GDI',checks=[])
            def render(name,sequence):
                write_snapshot(control,dict(phase=name,sequence=sequence+'\x1b[5n'))
                wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('phase')==name and bytes.fromhex(v.get('hex','')).endswith(b'\x1b[0n'))
                time.sleep(.15)
            def compare(name):
                pixels=capture(hwnd,f'renderer-{requested}-{name}.png',True)
                if not requested:references[name]=pixels
                else:
                    expected=references[name]
                    mismatch=sum(a!=b for a,b in zip(pixels,expected))
                    # Windows ClearType on a memory DC can round a channel by
                    # up to two compared with the display DC, especially fallback
                    # glyphs. Geometry, solid colours and retained repaints
                    # remain strict; do not mask shifts or missing glyphs.
                    error=max(abs(a-b) for a,b in zip(pixels,expected))
                    assert len(pixels)==len(expected) and error<=2 and mismatch<=len(pixels)//1000,(name,mismatch,error)
                    mode['checks'].append(dict(scene=name,changed_channels=mismatch,max_channel_error=error))
                if not requested:mode['checks'].append(dict(scene=name))
                return pixels
            text=('\x1b[?25l\x1b[0m\x1b[2J\x1b[HASCII abc XYZ 0123\r\n'
                  '中文 e\u0301 A\u0308 \U0001f680 \ue0b0\r\n'
                  '\x1b[1;3;4:3;58:2::255:80:0mBold italic curly\x1b[0m\r\n'
                  '\x1b[7;9mReverse strike\x1b[0m\r\n'
                  '\x1b[38;2;90;180;220;48;2;32;40;48mTruecolour\x1b[0m\r\n'
                  '\x1b#6Double width\r\n\x1b#3Double height\r\n\x1b#4Double height\r\n')
            render('text',text);base=compare('text')
            # An expose must preserve both unchanged glyphs and the cached frame.
            u.RedrawWindow(hwnd,None,None,0x185);time.sleep(.1)
            assert capture(hwnd,return_pixels=True)==base
            render('sixel',scene('SIXEL GPU composition','100;25;0'));base=compare('sixel')
            render('sync','\x1b[?2026h\x1b[Hhidden during synchronized update')
            u.RedrawWindow(hwnd,None,None,0x185)
            assert capture(hwnd,return_pixels=True)==base
            render('sync-end','\x1b[?2026l');compare('sync-end')
            outer,client=w.RECT(),w.RECT()
            u.GetWindowRect(hwnd,c.byref(outer));u.GetClientRect(hwnd,c.byref(client))
            cw,ch=(client.right-2)//80,(client.bottom-2)//24
            u.MoveWindow(hwnd,outer.left,outer.top,outer.right-outer.left+10*cw,
                         outer.bottom-outer.top+4*ch,True)
            wait_for(lambda:(read_snapshot(report) or {}).get('columns')==90)
            time.sleep(.2)
            compare('resize')
            # Palette changes must invalidate old cached run colours.
            render('palette','\x1b]10;#00ff80\x07\x1b]11;#101820\x07'+text)
            compare('palette')
            for shape in (2,4,6):
                render('cursor-'+str(shape),'\x1b[?12l\x1b['+str(shape)+' q\x1b[?25h\x1b[2;4H')
                u.SendMessageW(hwnd,0x8,0,0) # consistent inactive cursor on owned windows
                time.sleep(.1)
                compare('cursor-'+str(shape))
            assert int(u.GetPropW(hwnd,'NemotermRenderer'))==active,'Renderer failed during drawing'
            handle=k.OpenProcess(0x410,False,process.pid)
            try:mode['memory']=memory_sample(handle)
            finally:k.CloseHandle(handle)
            evidence['modes'].append(mode)
        finally:
            write_snapshot(control,dict(stop=True))
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,path)
(root/'research/renderer-observed.json').write_text(json.dumps(evidence,indent=2))
print('GDI/OpenGL pixel parity, text, Sixel, resize, expose and synchronized update passed:',[(v['active'],v['memory']) for v in evidence['modes']])
