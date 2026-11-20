"""Observe the OS cursor and the byte actually received by a hosted Windows child."""
import ctypes as c
import json
import os
from pathlib import Path
import time
from native_test_utils import w,u,root,terminal_host,wait_for
from hosted_gesture_input import DesktopInput
from protocol_oracle_window import run
from pointer_hiding_cases import cases


class CursorInfo(c.Structure):
    _fields_=[('size',w.DWORD),('flags',w.DWORD),('cursor',w.HANDLE),('position',w.POINT)]


def observe():
    v=CursorInfo(size=c.sizeof(CursorInfo));assert u.GetCursorInfo(c.byref(v))
    return dict(flags=v.flags,cursor=v.cursor,visible=bool(v.flags & 1 and v.cursor),position=[v.position.x,v.position.y])


def exercise(profile):
    def capture(hwnd,phase,current):
        pid=w.DWORD();assert u.GetWindowThreadProcessId(hwnd,c.byref(pid)); host=terminal_host(hwnd)
        assert host!=hwnd;result={'rows':[],'desktop':{},'profile_hide':profile};desk=DesktopInput(pid.value,host,hwnd,result['desktop'])
        def stable():
            readings=[]
            for delay in (.025,.04,.06):
                time.sleep(delay);readings.append(observe())
            assert len({r['visible'] for r in readings[-2:]})==1,readings
            return readings
        try:
            for name,seq,hidden in cases(bool(profile)):
                desk.point(45,55);phase(name,seq,b'');before=stable();desk.chord(ord('A'))
                data=wait_for(lambda: (r if (r:=current()).get('phase')==name and r.get('hex','').endswith('1b5b306e61') else None));after=stable()
                desk.point(61,55);moved=stable();positions=[r[-1]['position'] for r in (before,after,moved)];assert positions[0]==positions[1] and positions[1]!=positions[2]
                result['rows'].append(dict(name=name,sequence_hex=seq.encode().hex(),received=data['hex'],before=before,after=after,moved=moved,expected_hidden=hidden,
                    passed=before[-1]['visible'] and after[-1]['visible']!=hidden and moved[-1]['visible']))
        finally:desk.restore()
        return result
    return capture


if __name__=='__main__':
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted';u.GetCursorInfo.argtypes=[c.POINTER(CursorInfo)];failures={}
    for profile in (0,1):
        tag=f'pointer-hiding-{profile}';run(tag,[],exercise=exercise(profile),barrier=('\x1b[5n',b'\x1b[0n'),
            profile=dict(HideMousePtr=profile,NemoRenderer=0,NemoTabs=1,WarnOnClose=0,CloseOnExit=1),font=os.environ['NEMOTERM_TEST_FONT'],source_reference='XTerm 412 XTSMPOINTER')
        v=json.loads((root/'research'/(tag+'-observed.json')).read_bytes());assert v['completed'];rows=v['exercise']['rows'];assert len(rows)==len(cases(bool(profile)));failures[profile]=[r['name'] for r in rows if not r['passed']]
    assert not any(failures.values()),failures
