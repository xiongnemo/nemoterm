"""Observe a held local drag through scrollback using only the owned HWND."""
import ctypes as c
from ctypes import wintypes as w
from native_test_utils import u, time, wait_for


class ScrollInfo(c.Structure):
    _fields_=[('size',w.UINT),('mask',w.UINT),('low',c.c_int),('high',c.c_int),
              ('page',w.UINT),('pos',c.c_int),('track',c.c_int)]


def verify_history_drag(hwnd, begin_phase, point, capture, tile, copy, barrier, evidence):
    u.GetScrollInfo.argtypes=[w.HWND,c.c_int,c.POINTER(ScrollInfo)]
    lines=['R%02d:中e\u0301 END'%i for i in range(54)]
    scene='\x1b[?1049l\x1b[0m\x1b[?25l\x1b[2J\x1b[3J\x1b[H'+'\r\n'.join(lines)+'\x1b[?1002;1006h'
    cases=evidence['history_drags']=[]
    def scrollbar():
        s=ScrollInfo();s.size=c.sizeof(s);s.mask=7
        assert u.GetScrollInfo(hwnd,1,c.byref(s)), 'terminal has no vertical scrollbar'
        return (s.low,s.high,s.page,s.pos)
    for direction in ('up','down','takeover'):
        up=direction!='down';takeover=direction=='takeover'
        name='held-history-'+direction; record=dict(name=name,positions=[]);cases.append(record)
        begin_phase(name,scene)
        def loaded():
            info=scrollbar();record['range']=info
            return info if info[1]-info[0]+1==len(lines) and info[2]==24 else None
        wait_for(loaded)
        low,high,page,_=record['range'];bottom=high-page+1
        # Record the destination viewport before selection, then put the
        # real scrollbar at the opposite end. These are not the drag actions.
        start=bottom if up else low;goal=low if up else bottom
        u.SendMessageW(hwnd,0x115,6 if up else 7,0);wait_for(lambda:scrollbar()[3]==goal)
        x=0 if up else 2;y=0 if up else 23
        # Clearing any selection from the prior phase is itself a local click.
        u.SendMessageW(hwnd,0x201,5,point(16,12));u.SendMessageW(hwnd,0x202,4,point(16,12))
        time.sleep(.12);source=capture(name+'-before.png',return_pixels=True)
        u.SendMessageW(hwnd,0x115,7 if up else 6,0);wait_for(lambda:scrollbar()[3]==start)
        anchor=point(2,4) if up else point(0,20)
        # Exactly one motion beyond the client. No clock hook, fabricated
        # WM_TIMER, wheel, repeated movement or scroll messages while held.
        outside=(point(x,-2 if up else 25)&0xffffffff)
        # The takeover variant starts as an application press. Shift first
        # appears on the sole out-of-window move; no second move can help it.
        u.SendMessageW(hwnd,0x201,1 if takeover else 5,anchor);u.SendMessageW(hwnd,0x200,5,outside)
        try:
            until=time.monotonic()+5
            while time.monotonic()<until:
                p=scrollbar()[3]
                if not record['positions'] or p!=record['positions'][-1]:record['positions'].append(p)
                if p==goal:break
                time.sleep(.025)
        finally:u.SendMessageW(hwnd,0x202,4,outside)
        record['goal']=goal;record['final_position']=scrollbar()[3]
        time.sleep(.12);observed=capture(name+'-released.png',return_pixels=True)
        record['endpoint_highlighted']=tile(observed,x,y)!=tile(source,x,y)
        if not up:record['guard_unchanged']=tile(observed,3,y)==tile(source,3,y)
        record['expected']='\r\n'.join((lines[:34]+[lines[34][:3]]) if up else (lines[20:-1]+[lines[-1][:3]]))
        if takeover:record['expected']='\r\n'.join(lines[:30]+['R'])
        # If takeover never formed a selection, don't replace useful wire and
        # scrollbar evidence with a timeout waiting for a clipboard change.
        record['copied']=copy() if not takeover or record['final_position']==goal else None
        record['child_hex']=barrier(b'\x1b[<0;3;5M\x1b[<0;3;5m' if takeover else b'')
    assert all(r['final_position']==r['goal'] and len(r['positions'])>=3 and
               r['endpoint_highlighted'] and r.get('guard_unchanged',True) and
               r['copied']==r['expected'] for r in cases),cases
