"""Real user input scoped to one foreground terminal on a disposable Actions desktop."""
import os
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
        self.host,self.hwnd,self.record=host,hwnd,record
        self.u=u=c.WinDLL('user32',use_last_error=True)
        u.SendInput.argtypes=[w.UINT,c.POINTER(Input),c.c_int]
        u.WindowFromPoint.argtypes,u.WindowFromPoint.restype=[w.POINT],w.HWND
        u.GetForegroundWindow.restype=w.HWND
        u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
        u.GetGUIThreadInfo.argtypes=[w.DWORD,c.POINTER(ThreadInfo)]
        u.ClientToScreen.argtypes=[w.HWND,c.POINTER(w.POINT)]
        self.original=w.POINT();assert u.GetCursorPos(c.byref(self.original))
        owner=w.DWORD();self.thread=u.GetWindowThreadProcessId(hwnd,c.byref(owner));assert self.thread and owner.value==pid
        self.held=[];record['events']=[];record['focus']={}
        focus_owned_window(host,pid,mode='synchronized',record=record['focus'])
        self.target()
    def state(self):
        info=ThreadInfo(size=c.sizeof(ThreadInfo));assert self.u.GetGUIThreadInfo(self.thread,c.byref(info));return info
    def target(self):
        assert self.u.GetForegroundWindow()==self.host and self.state().focus==self.hwnd,'Terminal lost keyboard focus'
    def event(self,vk,down):
        if down:self.target()
        event=Input()
        if vk is None:event.kind=0;event.mouse.flags=2 if down else 4
        else:event.kind=1;event.key.key=vk;event.key.flags=0 if down else 2
        if self.u.SendInput(1,c.byref(event),c.sizeof(event))!=1:raise c.WinError(c.get_last_error())
        if down:self.held.append(vk)
        else:self.held.remove(vk)
        self.record['events'].append([vk if vk is not None else 'left',down])
    def chord(self,*keys):
        for key in keys:self.event(key,True)
        for key in reversed(keys):self.event(key,False)
    def point(self,x,y):
        p=w.POINT(x,y);assert self.u.ClientToScreen(self.hwnd,c.byref(p));assert self.u.SetCursorPos(p.x,p.y)
        wait_for(lambda:self.u.WindowFromPoint(p)==self.hwnd);return [p.x,p.y]
    def drag(self,x0,x1,y):
        self.record['start']=self.point(x0,y);self.event(0x10,True);self.event(None,True)
        wait_for(lambda:self.state().capture==self.hwnd);self.record['captured']=True
        self.record['end']=self.point(x1,y)
        self.event(None,False);wait_for(lambda:self.state().capture!=self.hwnd);self.event(0x10,False)
    def restore(self):
        try:
            for key in reversed(self.held[:]):self.event(key,False)
        finally:assert self.u.SetCursorPos(self.original.x,self.original.y)
