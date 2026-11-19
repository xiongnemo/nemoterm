"""Independent grid selections and Ctrl-drag rectangular copying and pixels."""
from native_test_utils import (root,c,w,u,hashlib,json,os,subprocess,sys,tempfile,
    Path,time,wait_for,find_window,read_snapshot,write_snapshot,wait_snapshot,capture,terminal_host)
from clipboard_test_utils import SavedClipboard,clipboard_text
from gpu_capture import OwnedGPUCapture
import argparse
import uuid
import winreg
parser=argparse.ArgumentParser()
parser.add_argument('--renderer',type=int,choices=(0,1,2),default=0)
parser.add_argument('--tabs',action='store_true')
parser.add_argument('--tab-side',choices=('top','bottom','left','right'),default='top')
font_options=parser.add_mutually_exclusive_group()
font_options.add_argument('--font',default=os.environ.get('NEMOTERM_TEST_FONT'))
font_options.add_argument('--profile-font',action='store_true',help='Leave the clean profile font unchanged')
args=parser.parse_args()
if args.profile_font:args.font=None
u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
u.GetClassNameW.argtypes=[w.HWND,w.LPWSTR,c.c_int]
profile='selection-'+uuid.uuid4().hex
keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:
    winreg.SetValueEx(key,'NemoRenderer',0,winreg.REG_DWORD,args.renderer)
    winreg.SetValueEx(key,'WarnOnClose',0,winreg.REG_DWORD,0)
    for setting,value in (('LogType',2),('LogFileClash',1),('LogFlush',1)):
        winreg.SetValueEx(key,setting,0,winreg.REG_DWORD,value)
    winreg.SetValueEx(key,'LogFileName',0,winreg.REG_SZ,str(root/'research/selection-child-output.log'))
exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
evidence=dict(requested_tab_host=args.tabs,tab_host=None,tab_side=args.tab_side,executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),checks=[],rectangles=[],requested_renderer=args.renderer,completed=False)
evidence['requested_font']=args.font
with tempfile.TemporaryDirectory(prefix='nemoterm-selection-') as temporary:
    report,control=(Path(temporary)/name for name in ('report','control'))
    process=subprocess.Popen([str(exe)]+(['--tabs','--tab-side',args.tab_side] if args.tabs else ['--no-tabs'])+(['--font',args.font] if args.font else [])+['-load',profile,'--cols','80','--rows','24','-e',sys.executable,
        str(root/'tests/mouse_fixture.py'),str(report),str(control),'150'],
        env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_UTF8_INPUT='1'),creationflags=subprocess.CREATE_NO_WINDOW)
    saved=None; session=None; script=None; gpu=None
    try:
        hwnd=wait_for(lambda:find_window(process.pid));wait_for(lambda:read_snapshot(report))
        host=terminal_host(hwnd);host_class=c.create_unicode_buffer(128)
        assert u.GetClassNameW(host,host_class,len(host_class))
        evidence['host_class']=host_class.value;evidence['tab_host']=host!=hwnd
        assert evidence['tab_host']==args.tabs and host_class.value==('NemotermHost' if args.tabs else 'Nemoterm'),evidence
        active=int(u.GetPropW(hwnd,'NemotermRenderer') or 0)
        assert active in (1,2,3)
        if args.renderer==0:assert active==1
        if args.renderer==2 and os.environ.get('NEMOTERM_REQUIRE_DIRECTX')=='1':assert active==3
        evidence['active_renderer']=active
        saved=SavedClipboard(hwnd)
        if active in (2,3):gpu=OwnedGPUCapture(process.pid,hwnd)
        import frida
        session=frida.attach(process.pid)
        script=session.create_script((root/'tests/agent_key_probe.js').read_text())
        errors=[]
        script.on('message',lambda message,data:errors.append(message) if message.get('type')=='error' else None)
        script.load();script.exports_sync.isolate_mouse(hex(hwnd));serial=0
        def captured(name=None,return_pixels=False):
            return gpu.capture(name,return_pixels) if gpu else capture(hwnd,name,return_pixels)
        phase_request=None
        def begin_phase(name,sequence,*,preserve_mouse=False):
            global phase_request
            phase_request=dict(phase=name,sequence=sequence+'\x1b[5n',preserve_mouse=preserve_mouse)
            write_snapshot(control,phase_request)
            return wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('phase')==name and bytes.fromhex(v.get('hex','')).endswith(b'\x1b[0n'))
        def tracked_phase(name,sequence):
            if name.endswith(('-scroll','-right')):
                # Prove BOTH application mouse modes are still set immediately
                # before moving or right-clicking. Store the untouched responses.
                probe=begin_phase(name+'-modes',sequence+'\x1b[?1002$p\x1b[?1006$p',preserve_mouse=True)
                evidence.setdefault('tracked_selection_phases',{})[name]=probe['hex']
                assert bytes.fromhex(probe['hex'])==b'\x1b[?1002;1$y\x1b[?1006;1$y\x1b[0n',(name,probe)
                sequence=''  # next acknowledgement opens the gesture's raw-input interval
            return begin_phase(name,sequence,preserve_mouse=True)
        def no_forwarded_input(expected_mouse=b''):
            # The fixture may briefly deny a mailbox read during atomic
            # replacement. Retain one complete acknowledged snapshot, and
            # drain preceding mouse/key input before asserting its exact bytes.
            barrier=phase_request['phase']
            write_snapshot(control,dict(phase_request,input_barrier=barrier))
            value=wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('phase')==barrier and v.get('input_barrier')==barrier and 'hex' in v)
            if expected_mouse is not None:
                assert bytes.fromhex(value['hex'])==b'\x1b[0n'+expected_mouse+b'\x1b[0n',value
            return value['hex']
        r=w.RECT();u.GetClientRect(hwnd,c.byref(r));cw,ch=(r.right-2)//80,(r.bottom-2)//24
        evidence['cell_pixels']=[cw,ch]
        def select(x,y,end):
            start=(1+y*ch+ch//2)<<16|(1+x*cw+cw//2)
            finish=(1+y*ch+ch//2)<<16|(1+end*cw+cw//2)
            u.SendMessageW(hwnd,0x201,5,start);u.SendMessageW(hwnd,0x200,5,finish)
            u.SendMessageW(hwnd,0x202,4,finish)
            previous=u.GetClipboardSequenceNumber()
            u.SendMessageW(hwnd,0x204,2,start);u.SendMessageW(hwnd,0x205,0,start)
            wait_for(lambda:u.GetClipboardSequenceNumber()!=previous)
            return clipboard_text(hwnd)
        for mode in ('legacy','application-mouse'):
            sequence='\x1b[?1000;1002;1003l\x1b[2J\x1b[HABCDEFGHIJ\r\n\r\n0123456789'
            if mode=='application-mouse':sequence+='\x1b[?1003;1006h'
            begin_phase(mode,sequence)
            # Desktop motion is outside this deterministic input fixture.
            # The queued message is ignored; synchronous actions below are not.
            assert u.PostMessageW(hwnd,0x200,0,(ch//2)<<16|(cw//2))
            # Synchronous messages deliberately share a short time interval;
            # only the changed coordinates distinguish these from multi-clicks.
            values=[select(0,0,2),select(2,2,4),select(5,0,7),select(0,2,1)]
            assert values==['ABC','234','FGH','01'],(mode,values)
            evidence['checks'].append(dict(mode=mode,selections=values))
            no_forwarded_input()
        time.sleep(.1);captured('selection-window.png')
        # Check the default shortcut on the rectangular local selection. This
        # injects keys only on our owned terminal's UI thread, then restores its
        # state. Clipboard backup/restore still surrounds the entire fixture.
        def shortcut(vk,scan):
            global serial
            serial+=1
            script.exports_sync.key(dict(id=serial,key=vk,scan=scan,modifiers=[16,17,160,162]))
            assert u.PostMessageW(hwnd,0x8322,0,0)
            assert wait_for(lambda:script.exports_sync.result())==dict(id=serial)
            assert not errors,errors
        def copy_shortcut():
            before=u.GetClipboardSequenceNumber()
            shortcut(67,46)
            wait_for(lambda:u.GetClipboardSequenceNumber()!=before)
            return clipboard_text(hwnd)
        def point(x,y):return (1+y*ch+ch//2)<<16|(1+x*cw+cw//2)
        def tile(pixels,x,y):
            return b''.join(pixels[((1+y*ch+dy)*r.right+1+x*cw)*3:((1+y*ch+dy)*r.right+1+(x+1)*cw)*3] for dy in range(ch))
        expected='12345\r\nb中e\u0301F\r\nlmnop'
        for alternate in (False,True):
            for mode in ('legacy','application-mouse'):
                for corner in range(4):
                    name=f'rectangle-{alternate}-{mode}-{corner}'
                    sequence=('\x1b[?1049h' if alternate else '\x1b[?1049l')
                    sequence+='\x1b[?9;1000;1001;1002;1003l\x1b[?25l\x1b[0m\x1b[2J\x1b[H'
                    sequence+='0123456789\r\nab中e\u0301FGHIJ\r\nklmnopqrst'
                    if mode=='application-mouse':sequence+='\x1b[?1003;1006h'
                    begin_phase(name,sequence)
                    time.sleep(.1);before=captured(return_pixels=True)
                    x,y=(5 if corner&1 else 1),(2 if corner&2 else 0)
                    keys=9|(4 if mode=='application-mouse' else 0)
                    u.SendMessageW(hwnd,0x201,keys,point(x,y))
                    # The shape is fixed by the initial press. Both modifiers
                    # may be released while the owned drag remains local.
                    u.SendMessageW(hwnd,0x200,1,point(6-x,2-y))
                    u.SendMessageW(hwnd,0x202,0,point(6-x,2-y))
                    time.sleep(.1)
                    after=captured('selection-rectangle.png' if not alternate and mode=='legacy' and corner==0 else None,return_pixels=True)
                    for row in range(4):
                        for col in range(10):
                            selected=row<=2 and 1<=col<=5
                            assert (tile(before,col,row)!=tile(after,col,row))==selected,(name,col,row,selected)
                    copied=copy_shortcut()
                    assert copied==expected,(name,copied)
                    u.SendMessageW(hwnd,0x204,2,point(0,0));u.SendMessageW(hwnd,0x205,0,point(0,0))
                    assert clipboard_text(hwnd)==expected
                    no_forwarded_input()
                    evidence['rectangles'].append(dict(mode=mode,alternate=alternate,corner=corner,text=copied,pixels=True))
        # Under application mouse tracking, a displayed soft wrap must not
        # become a clipboard newline (or a padding space before a wide glyph).
        # A real hard break should survive copy and the client's bracketed paste.
        for alternate,tail,reverse,top in ((False,'ABC',False,6),(True,'AB',True,10)):
            name='linear-wrap-'+('wide-edge' if alternate else 'full-row')
            expected=tail+'中e\u0301Z\r\nEND'
            check=dict(mode=name,alternate=alternate,backwards=reverse,expected=expected)
            evidence.setdefault('wrapped_selections',[]).append(check)
            begin_phase(name,('\x1b[?1049h' if alternate else '\x1b[?1049l')+
                        f'\x1b[?7h\x1b[?25l\x1b[0m\x1b[2J\x1b[{top+1};1H'+
                        '.'*77+tail+'中e\u0301Z\r\nEND|\x1b[?1002;1006;2004h')
            # Locate actual ink on all three rows before comparing selection
            # pixels. Coordinates on the third row include the unselected |.
            def source_pixels():
                p=captured(return_pixels=True)
                return p if all(len(set(tile(p,x,y)))>1 for x,y in
                                [(77,top),(0,top+1),(3,top+2)]) else None
            try:before=wait_for(source_pixels)
            finally:captured(name+'-source.png')
            start,end=point(77,top),point(2,top+2)
            if reverse:start,end=end,start
            u.SendMessageW(hwnd,0x201,5,start);u.SendMessageW(hwnd,0x200,5,end);u.SendMessageW(hwnd,0x202,4,end)
            def highlighted():
                after=captured(return_pixels=True)
                probes=[(76,top,False),(77,top,True),(78,top,True),
                        (0,top+1,True),(1,top+1,True),(2,top+1,True),
                        (0,top+2,True),(2,top+2,True),(3,top+2,False)]
                return all((tile(after,x,y)!=tile(before,x,y))==changed for x,y,changed in probes)
            try:wait_for(highlighted)
            finally:captured(name+'.png')
            check['pixels']=True
            check['copied']=copy_shortcut()
            assert check['copied']==expected,check
            shortcut(86,47)
            dsr=b'\x1b[0n'; payload=b'\x1b[200~'+expected.replace('\r\n','\r').encode()+b'\x1b[201~'
            wait_snapshot(lambda:read_snapshot(report),lambda v:bytes.fromhex(v.get('hex','')).endswith(b'\x1b[201~'))
            write_snapshot(control,dict(phase_request,input_barrier=name))
            observed=wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('input_barrier')==name)
            check.update(child_hex=observed['hex'],input_cp=observed['input_cp'])
            assert bytes.fromhex(check['child_hex'])==dsr+payload+dsr,check
        # The locally handled right-up can go to another HWND. Drive only the
        # messages the terminal receives; the uninjected desktop case also
        # verifies the actual recipient of the missing up.
        rr=evidence['right_release_outside']={}
        begin_phase('right-copy-down','\x1b[?1049h\x1b[2J\x1b[5;3HLOCAL-COPY\x1b[?1002;1006h')
        start,end=point(2,4),point(6,4)
        u.SendMessageW(hwnd,0x201,5,start);u.SendMessageW(hwnd,0x200,5,end);u.SendMessageW(hwnd,0x202,4,end)
        rr['shortcut_copy']=copy_shortcut();assert rr['shortcut_copy']=='LOCAL',rr
        before=u.GetClipboardSequenceNumber();u.SendMessageW(hwnd,0x204,2,end)
        wait_for(lambda:u.GetClipboardSequenceNumber()!=before);rr['right_copy']=clipboard_text(hwnd)
        assert rr['right_copy']=='LOCAL',rr
        rr['local_wire']=no_forwarded_input()  # intentionally no right-up at this HWND
        begin_phase('right-app-pair','\x1b[?1049l\x1bc\x1b[?1002;1006h')
        u.SendMessageW(hwnd,0x204,2,point(7,4));u.SendMessageW(hwnd,0x205,0,point(7,4))
        try:rr['application_wire']=no_forwarded_input(b'\x1b[<2;8;5M\x1b[<2;8;5m')
        finally:u.SendMessageW(hwnd,0x1f,0,0)
        from selection_history_drag import verify_history_drag
        verify_history_drag(hwnd,begin_phase,point,captured,tile,copy_shortcut,no_forwarded_input,evidence)
        from selection_release_endpoint import verify_release_endpoint, verify_wide_boundary
        verify_release_endpoint(hwnd,begin_phase,point,captured,tile,shortcut,no_forwarded_input,evidence)
        verify_wide_boundary(hwnd,begin_phase,point,captured,tile,shortcut,no_forwarded_input,evidence)
        from selection_release_endpoint import verify_scaled_rows
        verify_scaled_rows(hwnd,begin_phase,point,captured,tile,shortcut,no_forwarded_input,evidence)
        from selection_bidi_rectangle import verify as verify_bidi
        verify_bidi(hwnd,begin_phase,point,captured,tile,shortcut,no_forwarded_input,evidence)
        verify_bidi(hwnd,begin_phase,point,captured,tile,shortcut,no_forwarded_input,evidence,block=False)
        from selection_cursor_updates import verify as verify_cursor_updates
        verify_cursor_updates(hwnd,begin_phase,point,captured,tile,no_forwarded_input,evidence)
        from selection_pressed_scroll import verify as verify_pressed_scroll
        verify_pressed_scroll(hwnd,begin_phase,point,captured,tile,copy_shortcut,no_forwarded_input,evidence)
        from selection_split_scroll import verify as verify_split_scroll
        split_messages_ok=verify_split_scroll(hwnd,tracked_phase,point,captured,tile,copy_shortcut,no_forwarded_input,evidence)
        from selection_discarded_scroll import verify as verify_discarded_scroll
        discard_ok=verify_discarded_scroll(hwnd,tracked_phase,point,captured,tile,copy_shortcut,no_forwarded_input,evidence)
        from selection_horizontal_press import verify as verify_horizontal_press
        horizontal_ok=verify_horizontal_press(hwnd,tracked_phase,point,captured,tile,copy_shortcut,no_forwarded_input,evidence)
        split_system_ok=True

        from selection_bidi_words import verify as verify_words
        words_ok=verify_words(hwnd,begin_phase,point,captured,tile,copy_shortcut,no_forwarded_input,evidence)
        if args.tabs:
            # Remove the synchronous-message fixture's queued-mouse filter;
            # the final gestures are Windows SendInput, including copy.
            script.unload();script=None;session.detach();session=None
            from hosted_gesture_input import DesktopInput
            desktop=DesktopInput(process.pid,host,hwnd,evidence.setdefault('split_system_input',{}))
            try:
                def system_copy():
                    seq=u.GetClipboardSequenceNumber();desktop.chord(0x11,0x10,ord('C'))
                    wait_for(lambda:u.GetClipboardSequenceNumber()!=seq)
                    return clipboard_text(hwnd)
                def await_new_input():
                    name=phase_request['phase']
                    wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('phase')==name and
                                  len(bytes.fromhex(v.get('hex','')))>len(b'\x1b[0n'))
                split_system_ok=verify_split_scroll(hwnd,tracked_phase,point,captured,tile,system_copy,no_forwarded_input,evidence,desktop,await_new_input)
                discard_ok=verify_discarded_scroll(hwnd,tracked_phase,point,captured,tile,system_copy,no_forwarded_input,evidence,desktop,await_new_input) and discard_ok
                horizontal_ok=verify_horizontal_press(hwnd,tracked_phase,point,captured,tile,system_copy,no_forwarded_input,evidence,desktop,await_new_input) and horizontal_ok
                words_ok=verify_words(hwnd,begin_phase,point,captured,tile,system_copy,no_forwarded_input,evidence,desktop) and words_ok
                from selection_height_resize import verify as verify_height_resize
                height_ok=verify_height_resize(host,hwnd,begin_phase,point,captured,tile,no_forwarded_input,desktop,evidence)
                from selection_screen_modes import verify as verify_screen_modes
                screen_ok=verify_screen_modes(hwnd,begin_phase,point,captured,tile,no_forwarded_input,desktop,evidence)
            finally:desktop.restore()
        assert split_messages_ok and split_system_ok, (evidence['split_scroll_press'],evidence.get('split_scroll_system'))
        assert discard_ok,evidence['discarded_scroll_press']
        assert horizontal_ok,[(r['case'],r.get('right_copy'),r.get('highlight')) for k in ('horizontal_press','horizontal_press_system') for r in evidence.get(k,[]) if not r['passed']]
        assert words_ok,[(r['case'],r.get('copied'),r.get('highlight')) for group in ('bidi_word_messages','bidi_word_system') for r in evidence.get(group,[]) if not r['passed']]
        if args.tabs:assert height_ok,evidence['height_selection']
        if args.tabs:assert screen_ok,evidence['screen_selection']
        evidence['completed']=True
        print('Rapid independent selections and 16 Ctrl rectangles, exact Unicode, shortcut/right-click copy and pixels passed')
    finally:
        if sys.exc_info()[0]:evidence['error']=repr(sys.exc_info()[1])
        (root/'research'/('tabs-selection-observed.json' if args.tabs else 'selection-observed.json')).write_text(json.dumps(evidence,indent=2))
        (root/'research/selection-last-snapshot.json').write_text(json.dumps(read_snapshot(report)))
        if gpu:gpu.close()
        if script:script.unload()
        if session:session.detach()
        if saved:saved.restore()
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
        write_snapshot(control,dict(stop=True))
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5);raise
