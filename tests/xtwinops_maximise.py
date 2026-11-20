"""Check XTWINOPS 9 against actual top-level HWND rectangles, never the child grid."""
import ctypes as c
from ctypes import wintypes as w
import time
from fixture_io import read_snapshot, wait_snapshot, write_snapshot
from native_test_utils import u


def check(host, work, control, report, mode, permitted):
    def state():
        r=w.RECT(); assert u.GetWindowRect(host,c.byref(r))
        return dict(rect=[r.left,r.top,r.right,r.bottom],zoomed=bool(u.IsZoomed(host)),
                    frame=u.GetWindowLongW(host,-16)&0x00c40000)
    base=state(); area=[work.left,work.top,work.right,work.bottom]
    assert not base['zoomed'] and base['frame'] & 0x00c00000
    evidence=mode['axis_maximise']=dict(initial=base,work=area,steps=[])
    def request(name,op,expected):
        tag='axis-maximise-'+name
        write_snapshot(control,dict(phase=tag,sequence='\x1b['+op+'t\x1b[5n'))
        response=wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('phase')==tag and v.get('hex')=='1b5b306e')
        row=dict(name=name,op=op,response=response['hex'],expected=expected);evidence['steps'].append(row)
        until=time.monotonic()+1.2; stable=None
        while True:
            actual=row['observed']=state();now=time.monotonic()
            if actual==expected:
                if stable is None:stable=now
                if now-stable>=.18:row['passed']=True;return
            else:stable=None
            if now>=until:row['passed']=False;return
            time.sleep(.025)
    try:
        if not permitted:
            for op in (1,2,3,0):request('denied-'+str(op),'9;'+str(op),base)
            return
        # Learn the OS's maximized frame; it can extend beyond rcWork by
        # invisible sizing borders. Single-axis modes use rcWork, keep their
        # caption, and must not change the other pair of outer coordinates.
        u.ShowWindow(host,3);both=state();assert both['zoomed'] and both['frame']==base['frame'];u.ShowWindow(host,9);assert state()==base
        x,y,r,b=base['rect'];l,t,right,bottom=area
        vert=dict(base,rect=[x,t,r,bottom]); horiz=dict(base,rect=[l,y,right,b]); assert len({tuple(s['rect']) for s in (base,vert,horiz,both)})==4
        for name,op,expected in [('vertical','9;2',vert),('vertical-again','9;2',vert),('horizontal','9;3',horiz),('restore','9;0',base),
                                 ('horizontal-first','9;3',horiz),('both','9;1',both),('restore-after-both','9;0',base),
                                 ('both-first','9;1',both),('vertical-from-both','9;2',vert),('default-restore','9',base)]:request(name,op,expected)
    finally:
        # Restore only this fixture's owned host before unrelated resize checks.
        if u.IsZoomed(host):u.ShowWindow(host,9)
        if state()['rect']!=base['rect']:
            x,y,r,b=base['rect'];assert u.SetWindowPos(host,0,x,y,r-x,b-y,0x14)
