"""Real mouse/keyboard drag on a disposable hosted Windows desktop; no injected hooks."""
import os
import re
from native_test_utils import c, w, u, k, time, wait_for, read_snapshot, write_snapshot, capture
from clipboard_test_utils import SavedClipboard, clipboard_text
from selection_history_drag import ScrollInfo


class GuiThread(c.Structure):
    _fields_=[('size',w.DWORD),('flags',w.DWORD),('active',w.HWND),('focus',w.HWND),
              ('capture',w.HWND),('menu',w.HWND),('sizing',w.HWND),('caret',w.HWND),('rect',w.RECT)]


def verify_gestures(host, seat, child, Input, out, evidence, publish, visible_text):
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    hwnd=seat['hwnd']; wrect=w.RECT(); assert u.GetClientRect(hwnd,c.byref(wrect))
    cols,rows=seat['cols'],seat['rows'];assert (cols,rows)==(80,24)
    cw,ch=(wrect.right-2)//cols,(wrect.bottom-2)//rows
    u.GetScrollInfo.argtypes=[w.HWND,c.c_int,c.POINTER(ScrollInfo)]
    u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
    u.GetGUIThreadInfo.argtypes=[w.DWORD,c.POINTER(GuiThread)]
    thread=u.GetWindowThreadProcessId(hwnd,None);assert thread
    original=w.POINT();assert u.GetCursorPos(c.byref(original))
    lines=['R%02d:中e\u0301 END'%i for i in range(54)]
    scene='\x1b[?1049l\x1b[0m\x1b[?25l\x1b[2J\x1b[3J\x1b[H'+'\r\n'.join(lines)+'\x1b[?1002;1006;2004h\x1b[5n'
    held=[];saved=SavedClipboard(hwnd);checks=evidence['physical_history']=[]
    def scroll():
        s=ScrollInfo();s.size=c.sizeof(s);s.mask=7;assert u.GetScrollInfo(hwnd,1,c.byref(s))
        return s.pos if s.high==53 and s.page==24 else -1
    def capture_owner():
        state=GuiThread(size=c.sizeof(GuiThread)); assert u.GetGUIThreadInfo(thread,c.byref(state));return state.capture
    def event(kind,code,down):
        e=Input();e.kind=kind
        if kind:e.key.key=code;e.key.flags=0 if down else 2
        else:e.mouse.flags=({0:2,1:8} if down else {0:4,1:16})[code]
        assert u.SendInput(1,c.byref(e),c.sizeof(e))==1
        if down:held.append((kind,code))
        else:held.remove((kind,code))
    def move(x,y):
        p=w.POINT(x,y);assert u.ClientToScreen(hwnd,c.byref(p));assert u.SetCursorPos(p.x,p.y)
        actual=w.POINT();assert u.GetCursorPos(c.byref(actual)) and (actual.x,actual.y)==(p.x,p.y),(actual,p)
        return p
    def shortcut(vk):
        assert u.GetForegroundWindow()==host
        for key in (0x11,0x10,vk):event(1,key,True)
        for key in (vk,0x10,0x11):event(1,key,False)
    try:
        for i,mode in enumerate(('copy-paste','reenter','release','cancel','application')):
            check=dict(mode=mode,positions=[]);checks.append(check);phase='native-history-'+mode
            request=dict(phase=phase,sequence=scene);write_snapshot(child['control'],request)
            def delivered():
                r=read_snapshot(child['report']) or {};return r if r.get('phase')==phase and bytes.fromhex(r.get('hex','')).endswith(b'\x1b[0n') else None
            wait_for(delivered);wait_for(lambda:scroll()==30)
            # Start even successive gestures on different cells, outside the
            # system double-click rectangle. The first anchor ends after R34.
            p=move(1+(2+i*3)*cw+cw//2,1+4*ch+ch//2)
            # Moving from the tab strip can first hit a transient window.
            # Wait for a real terminal hit before sending any system input.
            hits=check['initial_hits']=[]
            def initial_hit():
                h=u.WindowFromPoint(p);fg=u.GetForegroundWindow();name=c.create_unicode_buffer(128)
                if h:u.GetClassNameW(h,name,len(name))
                sample=dict(hwnd=h,window_class=name.value,foreground=fg)
                if not hits or hits[-1]!=sample:hits.append(sample)
                return h==hwnd and fg==host
            wait_for(initial_hit,timeout=3)
            assert u.GetForegroundWindow()==host
            if mode!='application':event(1,0x10,True)
            event(0,0,True);wait_for(lambda:capture_owner()==hwnd)
            move(1+cw//2,-6)
            if mode!='application':
                def scrolled():
                    pos=scroll();poslist=check['positions']
                    if not poslist or poslist[-1]!=pos:poslist.append(pos)
                    return pos==0 if mode=='copy-paste' else 0<pos<=26
                wait_for(scrolled,timeout=5)
            if mode=='reenter':move(1+cw//2,1+5*ch+ch//2)
            elif mode=='cancel':u.SendMessageW(hwnd,0x1f,0,0);wait_for(lambda:capture_owner()!=hwnd)
            elif mode=='release':event(0,0,False);wait_for(lambda:capture_owner()!=hwnd)
            # A re-entering move is queued. Take the endpoint after the queue
            # has settled, and far enough from either scroll limit to prove stop.
            if mode in ('release','reenter','cancel','application'):
                time.sleep(.12);samples=[scroll()]
                for _ in range(12):time.sleep(.03);samples.append(scroll())
                check['stationary_positions']=samples;assert len(set(samples))==1,samples
                assert samples[0]==30 if mode=='application' else 0<samples[0]<30
            if (0,0) in held:event(0,0,False)
            wait_for(lambda:capture_owner()!=hwnd)
            if (1,0x10) in held:event(1,0x10,False)
            if mode=='copy-paste':
                capture(hwnd,str(out/'physical-history-selection.png'))
                expected='\r\n'.join(lines[:34]+['R34']);before=u.GetClipboardSequenceNumber()
                shortcut(ord('C'));wait_for(lambda:u.GetClipboardSequenceNumber()!=before)
                check['copied']=clipboard_text(hwnd);assert check['copied']==expected,check
                shortcut(ord('V'))
                wait_for(lambda:bytes.fromhex((read_snapshot(child['report']) or {}).get('hex','')).endswith(b'\x1b[201~'))
            write_snapshot(child['control'],dict(request,input_barrier=phase))
            def acknowledged():
                last=read_snapshot(child['report']) or {};return last if last.get('input_barrier')==phase else None
            data=bytes.fromhex(wait_for(acknowledged)['hex']);check['hex']=data.hex();dsr=b'\x1b[0n'
            if mode=='application':
                body=data[len(dsr):-len(dsr)]; assert data.startswith(dsr) and data.endswith(dsr)
                reports=list(re.finditer(rb'\x1b\[<(\d+);(\d+);(\d+)([Mm])',body));check['mouse_reports']=[m[0].hex() for m in reports]
                assert b''.join(m[0] for m in reports)==body and len(reports)>=3,(body,reports)
                assert (reports[0][1],reports[0][4])==(b'0',b'M') and (reports[-1][1],reports[-1][4])==(b'0',b'm')
                assert any(m[1]==b'32' and m[4]==b'M' for m in reports[1:-1])
            else:
                payload=b'\x1b[200~'+check['copied'].replace('\r\n','\r').encode()+b'\x1b[201~' if mode=='copy-paste' else b''
                assert data==dsr+payload+dsr,(mode,data)
            check['passed']=True;publish()
        # If a local right click releases over another window, the terminal sees
        # no button-up. The next application's gesture still needs both edges.
        check=evidence['right_release_outside']={};dsr=b'\x1b[0n'
        def start_right_phase(name,sequence):
            request=dict(phase='native-right-'+name,sequence=sequence+'\x1b[5n')
            write_snapshot(child['control'],request)
            wait_for(lambda:(v:=read_snapshot(child['report']) or {}).get('phase')==request['phase'] and bytes.fromhex(v.get('hex','')).endswith(dsr))
            return request
        def confirm(request):
            key=request['phase'];write_snapshot(child['control'],dict(request,input_barrier=key))
            return bytes.fromhex(wait_for(lambda:v if (v:=read_snapshot(child['report']) or {}).get('input_barrier')==key else None)['hex'])
        def cell(x,y):
            p=move(1+x*cw+cw//2,1+y*ch+ch//2);wait_for(lambda:u.WindowFromPoint(p)==hwnd);return p
        request=start_right_phase('copy','\x1b[?1049h\x1b[0m\x1b[?25l\x1b[2J\x1b[5;3HLOCAL-COPY\x1b[?1002;1006h\x1b[?1004l')
        def visible_label():
            lines=visible_text().splitlines();return len(lines)>4 and lines[4][2:12]=='LOCAL-COPY'
        try:wait_for(visible_label)
        finally:check['source_text']=visible_text();capture(hwnd,str(out/'outside-source.png'));publish()
        def cells(image):
            return [b''.join(image[((1+4*ch+dy)*wrect.right+1+x*cw)*3:((1+4*ch+dy)*wrect.right+1+(x+1)*cw)*3] for dy in range(ch)) for x in range(1,8)]
        source=cells(capture(hwnd,return_pixels=True));cell(2,4);event(1,0x10,True);event(0,0,True);wait_for(lambda:capture_owner()==hwnd)
        cell(6,4)
        def highlighted():
            now=cells(capture(hwnd,return_pixels=True));check['highlight_cells']=[a!=b for a,b in zip(source,now)]
            return check['highlight_cells']==[False,True,True,True,True,True,False]
        try:wait_for(highlighted)
        finally:capture(hwnd,str(out/'outside-highlight.png'));publish()
        event(0,0,False);wait_for(lambda:capture_owner()!=hwnd);event(1,0x10,False)
        before=u.GetClipboardSequenceNumber();shortcut(ord('C'));wait_for(lambda:u.GetClipboardSequenceNumber()!=before)
        check['shortcut_copy']=clipboard_text(hwnd);assert check['shortcut_copy']=='LOCAL',check
        before=u.GetClipboardSequenceNumber();event(0,1,True)
        try:wait_for(lambda:u.GetClipboardSequenceNumber()!=before)
        finally:check.update(copied=clipboard_text(hwnd),clipboard_changes=[before,u.GetClipboardSequenceNumber()],capture_at_copy=capture_owner());publish()
        assert check['copied']=='LOCAL',check
        # Only these two owned windows may become foreground on the runner.
        dest=w.POINT(1+12*cw,1+3*ch);assert u.ClientToScreen(hwnd,c.byref(dest))
        u.CreateWindowExW.argtypes=[w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,c.c_int,c.c_int,c.c_int,c.c_int,w.HWND,w.HMENU,w.HINSTANCE,c.c_void_p]
        u.CreateWindowExW.restype=w.HWND;u.DestroyWindow.argtypes=[w.HWND]
        u.PeekMessageW.argtypes=[c.POINTER(w.MSG),w.HWND,w.UINT,w.UINT,w.UINT]
        u.SetCapture.argtypes=[w.HWND];u.SetCapture.restype=w.HWND;u.GetCapture.restype=w.HWND
        u.DispatchMessageW.argtypes=[c.POINTER(w.MSG)];u.DispatchMessageW.restype=c.c_ssize_t
        u.AttachThreadInput.argtypes=[w.DWORD,w.DWORD,w.BOOL]
        own_thread=k.GetCurrentThreadId();assert thread!=own_thread
        sink=u.CreateWindowExW(0x88,'BUTTON','release target',0x90000000,dest.x-12,dest.y-12,24,24,None,None,None,None)
        assert sink
        attached=False
        try:
            assert u.SetCursorPos(dest.x,dest.y);wait_for(lambda:u.WindowFromPoint(dest)==sink)
            # Another UI can legitimately capture a locally handled mouse-up.
            # Give only our own sink the capture and service its full queue:
            # filtering for UP alone can leave the preceding input unprocessed.
            assert u.AttachThreadInput(own_thread,thread,True);attached=True
            u.SetForegroundWindow(sink);wait_for(lambda:u.GetForegroundWindow()==sink)
            u.SetCapture(sink);check['sink_owns_capture']=u.GetCapture()==sink and capture_owner()==sink
            check['foreground_at_release']=u.GetForegroundWindow()==sink;assert check['sink_owns_capture']
            check['right_was_down']=bool(u.GetAsyncKeyState(2)&0x8000);assert check['right_was_down']
            check['foreign_messages']=[];msg=w.MSG();event(0,1,False)
            def received_up():
                while u.PeekMessageW(c.byref(msg),None,0,0,1):
                    if msg.hWnd==sink:
                        if len(check['foreign_messages'])<60:check['foreign_messages'].append(msg.message)
                        if msg.message==0x205:return True
                    u.DispatchMessageW(c.byref(msg))
                return False
            wait_for(received_up);check['release_received_by_other_window']=True
        finally:
            if u.GetCapture()==sink:u.ReleaseCapture()
            if attached:
                try:u.SetForegroundWindow(host);wait_for(lambda:u.GetForegroundWindow()==host)
                finally:u.AttachThreadInput(own_thread,thread,False)
            u.DestroyWindow(sink);publish()
        check['local_wire']=confirm(request).hex();assert check['local_wire']==(dsr+dsr).hex(),check
        # RIS discards the selection. The peer requests button tracking again.
        request=start_right_phase('application','\x1b[?1049l\x1bc\x1b[?1002;1006h');assert u.GetForegroundWindow()==host
        cell(7,4);event(0,1,True);wait_for(lambda:capture_owner()==hwnd);event(0,1,False)
        expected=dsr+b'\x1b[<2;8;5M\x1b[<2;8;5m'+dsr
        observed=confirm(request);check.update(application_wire=observed.hex(),expected_wire=expected.hex(),capture_after_release=capture_owner());publish()
        try:assert observed==expected and check['capture_after_release']!=hwnd,check
        finally:
            if capture_owner()==hwnd:u.SendMessageW(hwnd,0x1f,0,0)
        check['passed']=True;publish()
    finally:
        for kind,code in reversed(held[:]):event(kind,code,False)
        u.SetCursorPos(original.x,original.y);saved.restore();publish()
