"""Owned GDI/OpenGL/DirectX windows: pixel parity, retained repaint, resize and sync.

Hardware is optional on CI: absence must take the working GDI fallback path.
Use NEMOTERM_REQUIRE_OPENGL=1 for the hardware acceptance run.
"""
from native_test_utils import *
from automation_capture import OwnedAutomationCapture
import uuid
import winreg
import atexit
import frida

exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
u.GetPropW.argtypes=[w.HWND,w.LPCWSTR];u.GetPropW.restype=w.HANDLE
font=os.environ.get('NEMOTERM_TEST_FONT','Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light')
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),font=font,modes=[],completed=False)
if 'NEMOTERM_TEST_DIAGNOSTIC_VARIANT' in os.environ:
    evidence['diagnostic_variant']=os.environ['NEMOTERM_TEST_DIAGNOSTIC_VARIANT']
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
        process=subprocess.Popen([str(exe),'-load',profile,'--automation','--cols','80','--rows','24',
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
            if active in (2,3):gl_capture=OwnedAutomationCapture(process.pid,hwnd)
            mode['capture_method']='public automation API' if gl_capture else 'PrintWindow explicit client render'
            mode['capture_injected']=False
            mode['focus_injected']=True
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
            text+=('\x1b[21;58:2::80:180:255mLegacy double underline\x1b[0m\r\n'
                   '\x1b[4;21mIndependent single and double\x1b[0m\r\n'
                   '\x1b[4:3;58:2::255:80:0m\x1b[21#{\x1b[21m\x1b[#}'
                   'Selective pop restores curly\x1b[0m\r\n')
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
            # More distinct equal-size runs than the 256-entry GPU cache.
            # Alternate every tile's contents, then restore them. Pending
            # draws must keep their old pixels when an evicted bitmap is reused.
            for cycle,variant in enumerate((0,1,0)):
                tiles='\x1b[0m\x1b[?25l\x1b[2J'
                for row in range(20):
                    tiles+=f'\x1b[{row+1};1H\x1b#5'
                    for column in range(40):
                        value=row*40+column+variant*800
                        red,green,blue=value%251,(value//251)*31,(value*43)%251
                        tiles+=f'\x1b[38;2;255;255;255;48;2;{red};{green};{blue}m'+('XY' if variant==0 else 'AB')
                name=f'cache-eviction-{cycle}'
                render(name,tiles+'\x1b[0m');compare(name)
            # Explicit semantic pixel check in addition to renderer parity:
            # eight overlined blank cells, eight cancelled cells, and concealed
            # cells below. Underline colour must not recolour the overline.
            overline=('\x1b[?25l\x1b[0m\x1b[2J\x1b[H'
                      '\x1b[38;2;81;177;221;48;2;10;20;30;58;2;255;0;0;53m'+
                      ' '*8+'\x1b[55m'+' '*8+'\r\n\x1b[53;8m'+' '*8+'\x1b[0m')
            render('overline',overline);pixels=compare('overline')
            dimensions=w.RECT();assert u.GetClientRect(hwnd,c.byref(dimensions))
            def pixel(px,py):
                offset=(py*dimensions.right+px)*3
                return pixels[offset:offset+3]
            for column in range(16*cw):
                assert pixel(1+column,1)==bytes((81,177,221) if column<8*cw else (10,20,30))
            for column in range(8*cw):
                assert pixel(1+column,1+ch)==bytes((10,20,30))
            double=('\x1b[0m\x1b[38;2;81;177;221;48;2;10;20;30;53m'
                    '\x1b[3;1H\x1b#6'+' '*8+'\x1b[4;1H\x1b#3'+' '*8+
                    '\x1b[5;1H\x1b#4'+' '*8+'\x1b[6;1H\x1b[7m'+' '*8+'\x1b[0m')
            render('overline-double-size',double);pixels=compare('overline-double-size')
            for column in range(16*cw):
                for row in (2,3):assert pixel(1+column,1+row*ch)==bytes((81,177,221))
                assert pixel(1+column,1+4*ch)==bytes((10,20,30))
            for column in range(8*cw):
                assert pixel(1+column,1+5*ch)==bytes((10,20,30))
                assert pixel(1+column,2+5*ch)==bytes((81,177,221))
            mode['overline_pixels_checked']=True
            # Enclosures must survive attribute-run splitting and distinguish
            # a frame from an unfilled ellipse. Solid-color blank cells give
            # independent geometry assertions, beyond renderer agreement.
            colours='\x1b[38;2;81;177;221;48;2;10;20;30;58;2;255;0;0m'
            enclosure=('\x1bc\x1b[?25l'+colours+'\x1b[51m'+' '*3+
                       '\x1b[54m'+' '*2+'\x1b[52m'+' '*3+'\x1b[54m'+' '*2+
                       '\x1b[2;1H\x1b[51;52m '+'\x1b[54m'+
                       '\x1b[3;1H\x1b[51;8m'+' '*3+'\x1b[28;54m'+
                       '\x1b[4;1H\x1b[51;7m  \x1b[27;54m'+
                       '\x1b[5;1H\x1b[51m\u3000\x1b[54m'+
                       '\x1b[6;1H\x1b[51me\u0301\x1b[54m')
            render('enclosures',enclosure);pixels=compare('enclosures')
            ink, paper=bytes((81,177,221)),bytes((10,20,30))
            def frame(left,top,width,height,foreground=ink,background=paper,blank=True):
                for yy in range(height):
                    for xx in range(width):
                        edge=xx in (0,width-1) or yy in (0,height-1)
                        if edge or blank:
                            assert pixel(left+xx,top+yy)==(foreground if edge else background),(left,top,xx,yy)
            def ellipse(left,top,width,height):
                border=[pixel(left+x,top+y) for x,y in
                        ((0,0),(width-1,0),(0,height-1),(width-1,height-1))]
                assert all(v==paper for v in border)
                assert pixel(left+width//2,top+height//2)==paper
                assert ink in [pixel(left+x,top) for x in range(width)]
                assert ink in [pixel(left+x,top+height-1) for x in range(width)]
                assert ink in [pixel(left,top+y) for y in range(height)]
                assert ink in [pixel(left+width-1,top+y) for y in range(height)]
                assert all(pixel(left+x,top+y) in (ink,paper)
                           for y in range(height) for x in range(width))
            for column in range(3):frame(1+column*cw,1,cw,ch)
            for column in (3,4,8,9):
                assert all(pixel(1+column*cw+x,1+y)==paper for y in range(ch) for x in range(cw))
            for column in range(5,8):ellipse(1+column*cw,1,cw,ch)
            frame(1,1+ch,cw,ch,blank=False)
            assert any(pixel(1+x,1+ch+y)==ink for y in range(1,ch-1) for x in range(1,cw-1))
            assert all(pixel(1+x,1+2*ch+y)==paper for y in range(ch) for x in range(3*cw))
            for column in range(2):frame(1+column*cw,1+3*ch,cw,ch,paper,ink)
            frame(1,1+4*ch,2*cw,ch)
            frame(1,1+5*ch,cw,ch,blank=False)
            double_enclosure=(colours+'\x1b[51m\x1b[7;1H\x1b#6   '+
                              '\x1b[8;1H\x1b#3  \x1b[9;1H\x1b#4  '+
                              '\x1b[54;52m\x1b[11;1H\x1b#3  '+
                              '\x1b[12;1H\x1b#4  \x1b[54m')
            render('enclosures-double-size',double_enclosure);pixels=compare('enclosures-double-size')
            for column in range(3):frame(1+column*2*cw,1+6*ch,2*cw,ch)
            for column in range(2):
                frame(1+column*2*cw,1+7*ch,2*cw,2*ch)
                ellipse(1+column*2*cw,1+10*ch,2*cw,2*ch)
            mode['enclosure_pixels_checked']=True
            # Horizontal ideogram decorations have a separate SGR lifetime and
            # use foreground colour, even when SGR 58 selects another colour.
            ideogram='\x1bc\x1b[?25l'+colours
            for row,code in enumerate(range(60,65),1):
                ideogram+=f'\x1b[{row};1H\x1b[{code}m   \x1b[65m  '
            ideogram+=('\x1b[6;1H\x1b[60;61;62;63;64m   \x1b[65m'+
                       '\x1b[7;1H   \x1b[8;1H\x1b[60;61;62;63;64;8m   \x1b[28;65m'+
                       '\x1b[9;1H\x1b[60;7m   \x1b[27;65m'+
                       '\x1b[10;1H\x1b[61m\u3000\x1b[65m'+
                       '\x1b[11;1H\x1b[64m\u3000\x1b[65m')
            render('ideograms',ideogram);pixels=compare('ideograms')
            def ideogram_cell(left,top,width,height,aspects,foreground=ink,background=paper):
                thickness=max(1,ch//16)
                lower=set();upper=set()
                if 60 in aspects or 61 in aspects:lower.update(range(height-thickness,height))
                if 61 in aspects:lower.update(range(height-3*thickness,height-2*thickness))
                if 62 in aspects or 63 in aspects:upper.update(range(thickness))
                if 63 in aspects:upper.update(range(2*thickness,3*thickness))
                size=min(2*thickness,width,height)
                mark_x=(width-size)//2;mark_y=min(thickness,height-size)
                for yy in range(height):
                    for xx in range(width):
                        marked=(64 in aspects and mark_x<=xx<mark_x+size and mark_y<=yy<mark_y+size)
                        expected=foreground if yy in lower or yy in upper or marked else background
                        assert pixel(left+xx,top+yy)==expected,(left,top,width,height,aspects,xx,yy)
            for row,code in enumerate(range(60,65)):
                for column in range(3):ideogram_cell(1+column*cw,1+row*ch,cw,ch,{code})
                for column in (3,4):ideogram_cell(1+column*cw,1+row*ch,cw,ch,set())
            for column in range(3):
                ideogram_cell(1+column*cw,1+5*ch,cw,ch,set(range(60,65)))
                ideogram_cell(1+column*cw,1+6*ch,cw,ch,set())
                ideogram_cell(1+column*cw,1+7*ch,cw,ch,set())
                ideogram_cell(1+column*cw,1+8*ch,cw,ch,{60},paper,ink)
            ideogram_cell(1,1+9*ch,2*cw,ch,{61})
            ideogram_cell(1,1+10*ch,2*cw,ch,{64})
            double_ideogram=('\x1b[0m'+colours+'\x1b[60;64m\x1b[14;1H\x1b#6   '+
                             '\x1b[65;61;62;64m\x1b[15;1H\x1b#3  \x1b[16;1H\x1b#4  '+
                             '\x1b[65m\x1b[17;1H\x1b#3  \x1b[18;1H\x1b#4  '+
                             '\x1b[19;1H\x1b[64me\u0301\x1b[65m')
            render('ideograms-double-size',double_ideogram);pixels=compare('ideograms-double-size')
            for column in range(3):ideogram_cell(1+column*2*cw,1+13*ch,2*cw,ch,{60,64})
            for column in range(2):
                ideogram_cell(1+column*2*cw,1+14*ch,2*cw,2*ch,{61,62,64})
                ideogram_cell(1+column*2*cw,1+16*ch,2*cw,2*ch,set())
            mode['ideogram_pixels_checked']=True
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
