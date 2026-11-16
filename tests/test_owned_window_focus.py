"""Deterministic deferred-activation and input-delivery regression controls.

All window/input calls are replaced; this suite never touches the desktop.
The model exposes two independent native API contracts, not Windows timing:
activation can be deferred until the target queue runs, and inserting input
does not mean the input has been delivered. Hosted replay checks real Windows.
"""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import owned_window_focus as focus


class Desktop:
    target = 101
    def __init__(self, accepted=False, responsive=True):
        self.foreground=202;self.accepted=accepted;self.responsive=responsive
        self.pending_activation=False;self.pending_click=False
        self.cursor=(900,800);self.topmost=False;self.clicks=0;self.barriers=0
        self.input_delivery=[];self.foreground_calls=0

    def IsWindow(self,window):return window==self.target
    def GetWindowThreadProcessId(self,window,pid):pid._obj.value=42;return 7
    def GetForegroundWindow(self):return self.foreground
    def SetForegroundWindow(self,window):
        self.foreground_calls+=1
        self.pending_activation=self.accepted
        return self.accepted
    def SendMessageTimeoutW(self,*unused):
        self.barriers+=1
        if self.responsive and self.pending_activation:self.foreground=self.target
        return int(self.responsive)
    def GetWindowLongPtrW(self,window,index):return int(self.topmost)*8 if index==-20 else 0x00CF0000
    def GetCursorPos(self,point):point._obj.x,point._obj.y=self.cursor;return 1
    def SetCursorPos(self,x,y):self.cursor=(x,y);return 1
    def SetWindowPos(self,window,after,*unused):self.topmost=after==-1;return 1
    def GetWindowRect(self,window,bounds):
        bounds._obj.left=100;bounds._obj.top=100
        bounds._obj.right=500;bounds._obj.bottom=400
        return 1
    def WindowFromPoint(self,point):return self.target if self.topmost and point.y<160 else 202
    def SendMessageW(self,*unused):return 2  # Owned, exposed caption
    def SendInput(self,count,*unused):self.pending_click=True;self.clicks+=count;return count
    def GetAsyncKeyState(self,key):return 0
    def GetSystemMetrics(self,index):return {76:0,77:0,78:1024,79:768}[index]
    def GetDoubleClickTime(self):return 500
    def wait(self,predicate):
        # Advancing the desktop delivers pending input at its current position.
        if self.pending_click:
            delivered=self.target if self.topmost and self.cursor==(300,106) else 202
            self.input_delivery.append(delivered);self.foreground=delivered
            self.pending_click=False
        if not predicate():raise TimeoutError('Modeled desktop did not activate the target')


class FocusContracts(unittest.TestCase):
    def invoke(self,desktop,record,mode='synchronized',pid=42):
        with patch.object(focus,'u',desktop), patch.object(focus,'terminal_host',lambda hwnd:hwnd), \
             patch.object(focus,'wait_for',desktop.wait), patch.object(focus,'time',SimpleNamespace(monotonic=lambda:1.,sleep=lambda seconds:None)):
            return focus.focus_owned_window(desktop.target,pid,allow_local=True,record=record,mode=mode)

    def test_deferred_activation_needs_no_click_after_queue_barrier(self):
        desktop=Desktop(accepted=True);record={}
        self.invoke(desktop,record)
        self.assertEqual((desktop.barriers,desktop.clicks),(1,0))
        self.assertTrue(record['completed'])

    def test_deferred_input_delivers_before_cursor_and_stacking_restore(self):
        desktop=Desktop();record={}
        self.invoke(desktop,record)
        self.assertEqual(desktop.input_delivery,[desktop.target])
        self.assertEqual((desktop.cursor,desktop.topmost),((900,800),False))
        self.assertTrue(record['completed'])

    def test_legacy_order_is_negative_control_and_retains_failure(self):
        desktop=Desktop();record={}
        with self.assertRaises(TimeoutError):self.invoke(desktop,record,'legacy')
        self.assertEqual(desktop.input_delivery,[202])
        self.assertEqual((desktop.cursor,desktop.topmost),((900,800),False))
        self.assertFalse(record['completed'])
        self.assertEqual(record['transitions'][-1]['stage'],'failed')

    def test_unresponsive_queue_fails_without_injecting_input(self):
        desktop=Desktop(accepted=True,responsive=False);record={}
        with self.assertRaises(AssertionError):self.invoke(desktop,record)
        self.assertEqual(desktop.clicks,0)
        self.assertFalse(record['completed'])
        self.assertIn('unresponsive',record['error'])

    def test_foreign_owner_is_rejected_before_any_foreground_action(self):
        desktop=Desktop();record={}
        with self.assertRaises(AssertionError):self.invoke(desktop,record,pid=99)
        self.assertEqual((desktop.foreground_calls,desktop.barriers,desktop.clicks),(0,0,0))

    def test_already_foreground_needs_no_queue_or_input(self):
        desktop=Desktop();desktop.foreground=desktop.target;record={}
        self.invoke(desktop,record)
        self.assertEqual((desktop.foreground_calls,desktop.barriers,desktop.clicks),(0,0,0))
        self.assertTrue(record['completed'])


if __name__=='__main__':unittest.main()
