"""Real user input scoped to one foreground terminal on a disposable Actions desktop."""
import os
import time
from native_test_utils import c, w, wait_for
from owned_window_focus import focus_owned_window


class MouseInput(c.Structure):
    _fields_ = [('x', w.LONG), ('y', w.LONG), ('data', w.DWORD),
                ('flags', w.DWORD), ('time', w.DWORD), ('extra', c.c_size_t)]

class KeyboardInput(c.Structure):
    _fields_ = [('key', w.WORD), ('scan', w.WORD), ('flags', w.DWORD),
                ('time', w.DWORD), ('extra', c.c_size_t)]

class InputUnion(c.Union):
    _fields_ = [('mouse', MouseInput), ('key', KeyboardInput)]

class Input(c.Structure):
    _anonymous_ = ('data',)
    _fields_ = [('kind', w.DWORD), ('data', InputUnion)]

class ThreadInfo(c.Structure):
    _fields_ = [('size',w.DWORD),('flags',w.DWORD),('active',w.HWND),('focus',w.HWND),
                ('capture',w.HWND),('menu',w.HWND),('sizing',w.HWND),('caret',w.HWND),('rect',w.RECT)]


class DesktopInput:
    def __init__(self,pid,host,hwnd,record):
        if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
            raise RuntimeError('System input is restricted to a GitHub-hosted desktop')
        self.pid,self.host,self.hwnd,self.record=pid,host,hwnd,record
        self.u=u=c.WinDLL('user32',use_last_error=True)
        u.SendInput.argtypes=[w.UINT,c.POINTER(Input),c.c_int]
        u.WindowFromPoint.argtypes,u.WindowFromPoint.restype=[w.POINT],w.HWND
        u.GetForegroundWindow.restype=w.HWND
        u.GetParent.argtypes,u.GetParent.restype=[w.HWND],w.HWND
        u.GetAncestor.argtypes,u.GetAncestor.restype=[w.HWND,w.UINT],w.HWND
        u.SendMessageTimeoutW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM,w.UINT,w.UINT,c.POINTER(c.c_size_t)]
        u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
        u.GetGUIThreadInfo.argtypes=[w.DWORD,c.POINTER(ThreadInfo)]
        u.ClientToScreen.argtypes=[w.HWND,c.POINTER(w.POINT)]
        u.GetWindow.argtypes,u.GetWindow.restype=[w.HWND,w.UINT],w.HWND
        u.GetDlgItem.argtypes,u.GetDlgItem.restype=[w.HWND,c.c_int],w.HWND
        u.GetWindowRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
        u.GetClassNameW.argtypes=[w.HWND,w.LPWSTR,c.c_int]
        u.IsWindowEnabled.argtypes=u.IsWindow.argtypes=[w.HWND]
        self.original=w.POINT();assert u.GetCursorPos(c.byref(self.original))
        owner=w.DWORD();self.thread=u.GetWindowThreadProcessId(hwnd,c.byref(owner));assert self.thread and owner.value==pid
        work=w.RECT();assert u.SystemParametersInfoW(0x30,0,c.byref(work),0)
        u.SetWindowPos.argtypes=[w.HWND,w.HWND,c.c_int,c.c_int,c.c_int,c.c_int,w.UINT]
        assert u.SetWindowPos(host,None,work.left+8,work.top+8,0,0,0x15)  # preserve size, order and activation
        self.held=[];record['events']=[];record['focus']={}
        focus_owned_window(host,pid,mode='synchronized',record=record['focus'])
        self.target()
    def state(self):
        info=ThreadInfo(size=c.sizeof(ThreadInfo));assert self.u.GetGUIThreadInfo(self.thread,c.byref(info));return info
    def target(self):
        assert self.u.GetForegroundWindow()==self.host and self.state().focus==self.hwnd,'Terminal lost keyboard focus'
    def owned_confirmation(self):
        win=self.u; hwnd=win.GetForegroundWindow(); owner=w.DWORD(); cls=c.create_unicode_buffer(64)
        thread=win.GetWindowThreadProcessId(hwnd,c.byref(owner));win.GetClassNameW(hwnd,cls,len(cls))
        if thread==self.thread and owner.value==self.pid and cls.value=='#32770' and win.GetWindow(hwnd,4)==self.host:
            return hwnd
    def click_confirmation_button(self,hwnd,button,log):
        win=self.u; assert self.owned_confirmation()==hwnd
        b=win.GetDlgItem(hwnd,button);r=w.RECT();assert b and win.GetWindowRect(b,c.byref(r))
        pt=w.POINT((r.left+r.right)//2,(r.top+r.bottom)//2)
        log.update(dialog=hwnd,button_id=button,button=b,point=[pt.x,pt.y],observations=[])
        start=time.monotonic()
        def observe(stage):
            current=w.POINT();assert win.GetCursorPos(c.byref(current))
            foreground=win.GetForegroundWindow();pid=w.DWORD()
            if foreground:win.GetWindowThreadProcessId(foreground,c.byref(pid))
            info=self.state();hit=win.WindowFromPoint(current);cls=c.create_unicode_buffer(100)
            if foreground:win.GetClassNameW(foreground,cls,len(cls))
            value=dict(stage=stage,foreground=foreground,foreground_pid=pid.value,foreground_class=cls.value,active=info.active,
                       focus=info.focus,capture=info.capture,cursor=[current.x,current.y],hit=hit,
                       dialog_alive=bool(win.IsWindow(hwnd)),button_alive=bool(win.IsWindow(b)),
                       host_enabled=bool(win.IsWindowEnabled(self.host)),left_down=bool(win.GetAsyncKeyState(1)&0x8000))
            # Keep changed states only. Never activate a window or repeat a missed click.
            history=log['observations']
            if not history or value!=history[-1]['state']:
                if len(history)<96:history.append(dict(ms=round(1000*(time.monotonic()-start)),state=value))
                else:log['last_overflow_state']=value
            return value
        def button_state(control):
            reply=c.c_size_t();assert win.SendMessageTimeoutW(control,0xf2,0,0,2,500,c.byref(reply))  # BM_GETSTATE
            return reply.value
        # A dialog can appear underneath an already stationary pointer. Enter
        # the button from elsewhere on this very dialog, as a real user would.
        # Never move through another application, click twice, or repair focus.
        def move_and_wait(x,y,stage,owned_hit,hot,control):
            if hot:
                # Model one approach through distinct interior pixels. A jump
                # to the centre alone can arrive before a freshly created
                # modal starts consuming button motion on the hosted desktop.
                bounds=w.RECT();assert win.GetWindowRect(control,c.byref(bounds))
                radius=min(12,(x-bounds.left)//2);assert radius>=3
                for dx in (-radius,-(2*radius//3),-(radius//3)):
                    if self.owned_confirmation()!=hwnd or not owned_hit(win.WindowFromPoint(w.POINT(x+dx,y))):
                        raise AssertionError('Another surface obscures the button approach')
                    self.move_screen(x+dx,y)
                    observe(stage+'-moving');time.sleep(.030)
            self.move_screen(x,y)
            def arrived():
                state=observe(stage);native=button_state(control);log[stage+'_state']=native
                return (state['cursor']==[x,y] and owned_hit(state['hit'])
                        and self.owned_confirmation()==hwnd and state['active']==hwnd
                        and not state['left_down'] and bool(native & 0x200)==hot)  # BST_HOT
            try: wait_for(arrived)
            finally: log[stage+'_end_ms']=round(1000*(time.monotonic()-start))
        def other_dialog_surface(h): return bool(h and h!=b and win.GetAncestor(h,2)==hwnd)
        observe('before-approach')
        approach=wait_for(lambda:next((q for q in [w.POINT(pt.x,r.top-3), w.POINT(r.left-3,pt.y),
                                   w.POINT(pt.x,r.bottom+2)]
                       if other_dialog_surface(win.WindowFromPoint(q))),None))
        log['approach']=[approach.x,approach.y]
        move_and_wait(approach.x,approach.y,'approach',other_dialog_surface,False,b)
        # WindowFromPoint alone cannot tell whether the dialog thread has
        # consumed this motion. Cross the other native button before entering
        # the target; require each control to acknowledge its own hover.
        sibling=win.GetDlgItem(hwnd,1 if button==2 else 2);sr=w.RECT()
        assert sibling and sibling!=b and win.GetWindowRect(sibling,c.byref(sr))
        sx,sy=(sr.left+sr.right)//2,(sr.top+sr.bottom)//2
        assert win.WindowFromPoint(w.POINT(sx,sy))==sibling
        log.update(sibling=sibling,sibling_point=[sx,sy])
        move_and_wait(sx,sy,'sibling_hover',lambda h:h==sibling,True,sibling)
        assert not button_state(b)&0x200
        move_and_wait(pt.x,pt.y,'hover',lambda h:h==b,True,b)

        # Wait for native button delivery before releasing, not merely SendInput insertion.
        down=Input();down.mouse.flags=2;up=Input();up.mouse.flags=4
        assert win.SendInput(1,c.byref(down),c.sizeof(Input))==1
        try:
            def pressed():
                state=observe('down');value=button_state(b)
                log.update(button_state=value,capture=state['capture'],focus=state['focus'])
                return state['capture']==b and bool(value & 4)  # BST_PUSHED
            wait_for(pressed,timeout=3)
        finally:
            assert win.SendInput(1,c.byref(up),c.sizeof(Input))==1
            observe('up-inserted')
    def event(self,vk,down,*,extended=False):
        if down:self.target()
        event=Input()
        if vk in (None, 'right', 'middle'):
            event.kind=0
            event.mouse.flags={None:(2,4), 'right':(8,16), 'middle':(32,64)}[vk][not down]
        else:event.kind=1;event.key.key=vk;event.key.flags=(0 if down else 2) | (1 if extended else 0)
        if self.u.SendInput(1,c.byref(event),c.sizeof(event))!=1:raise c.WinError(c.get_last_error())
        if down:self.held.append(vk)
        else:self.held.remove(vk)
        self.record['events'].append([vk if vk is not None else 'left',down])
    def chord(self,*keys):
        for key in keys:self.event(key,True)
        for key in reversed(keys):self.event(key,False)
    def move_screen(self,x,y):
        u=self.u;left,top,width,height=[u.GetSystemMetrics(i) for i in (76,77,78,79)]
        assert left<=x<left+width and top<=y<top+height,(x,y,left,top,width,height)
        event=Input();event.kind=0;event.mouse.flags=0xc001|0x2000  # absolute virtual desktop; no coalescing
        event.mouse.x=((x-left)*65536+32768)//width;event.mouse.y=((y-top)*65536+32768)//height
        assert u.SendInput(1,c.byref(event),c.sizeof(event))==1
        return [left,top,width,height]
    def point(self,x,y):
        u=self.u;p=w.POINT(x,y);assert u.ClientToScreen(self.hwnd,c.byref(p))
        r=dict(client=[x,y],screen=[p.x,p.y],desktop=self.move_screen(p.x,p.y),observations=[])
        self.record.setdefault('motion',[]).append(r)
        def arrived():
            actual=w.POINT();assert u.GetCursorPos(c.byref(actual));hit=u.WindowFromPoint(actual)
            state=self.state();name=c.create_unicode_buffer(100)
            if hit:u.GetClassNameW(hit,name,len(name))
            obs=dict(point=[actual.x,actual.y],hit=hit,window_class=name.value,focus=state.focus,capture=state.capture)
            accepts=hit==self.hwnd
            # WindowFromPoint in the controller can return the renderer even
            # though its same-thread WM_NCHITTEST delegates actual input.
            if hit and name.value in ('NemotermDirect3D11','NemotermOpenGL') and u.GetParent(hit)==self.hwnd and u.GetWindowThreadProcessId(hit,None)==self.thread:
                reply=c.c_size_t();coords=(p.x&0xffff)|((p.y&0xffff)<<16)
                if u.SendMessageTimeoutW(hit,0x84,0,coords,2,300,c.byref(reply)):
                    obs['render_hit_test']=c.c_ssize_t(reply.value).value;accepts=obs['render_hit_test']==-1
            if not r['observations'] or r['observations'][-1]!=obs:r['observations'].append(obs)
            return (actual.x,actual.y)==(p.x,p.y) and accepts
        wait_for(arrived);return [p.x,p.y]
    def drag(self,x0,x1,y,highlight):
        self.record['start']=self.point(x0,y);self.event(0x10,True);self.event(None,True)
        wait_for(lambda:self.state().capture==self.hwnd);self.record['captured']=True
        self.point((x0+x1)//2,y);self.record['end']=self.point(x1,y)
        try:
            # An actual user can see the highlight before releasing. End the
            # gesture only after the last motion is consumed and painted.
            wait_for(highlight);self.record['highlight_while_held']=True
        finally:
            self.event(None,False);wait_for(lambda:self.state().capture!=self.hwnd);self.event(0x10,False)
    def restore(self):
        try:
            for key in reversed(self.held[:]):self.event(key,False)
        finally:assert self.u.SetCursorPos(self.original.x,self.original.y)
