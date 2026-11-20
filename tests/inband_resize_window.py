"""In-band resize: the child reads notifications and measures its native console grid."""
import ctypes as c
from ctypes import wintypes as w
import json
import os
import re
import traceback
from hosted_gesture_input import DesktopInput
from native_test_utils import root, terminal_host, u, wait_for
from protocol_oracle_window import run

CSI='\x1b['
ACK=b'\x1b[0n'
QUERY=CSI+'?2048$p'; ON=CSI+'?2048h'; OFF=CSI+'?2048l'
NOTICE=re.compile(rb'\x1b\[48;(\d+);(\d+);(\d+);(\d+)t')
BORDER=3


def trial(renderer,tabbed):
    name=f'column-mode-inband-{renderer}-'+('tabs' if tabbed else 'standalone'); rec={'checks':{},'observations':{}}
    def exercise(hwnd,phase,current):
        outer=terminal_host(hwnd);assert (outer!=hwnd)==tabbed
        pid=w.DWORD();u.GetWindowThreadProcessId(hwnd,c.byref(pid));u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
        rec['actual_renderer']=int(u.GetPropW(hwnd,'NemotermRenderer') or 0);assert rec['actual_renderer']=={'gdi':1,'directx':3}[renderer]
        u.SetWindowPos.argtypes=[w.HWND,w.HWND,c.c_int,c.c_int,c.c_int,c.c_int,w.UINT]
        desk=DesktopInput(pid.value,outer,hwnd,rec.setdefault('input',{}))
        def measure():
            v=current();cols,rows=v['columns'],v['rows'];r=w.RECT();assert u.GetClientRect(hwnd,c.byref(r));width,height=r.right,r.bottom
            return dict(rows=rows,cols=cols,width=width,height=height,cw=(width-2*BORDER)//cols,ch=(height-2*BORDER)//rows)
        def notice(g):return (CSI+f"48;{g['rows']};{g['cols']};{g['rows']*g['ch']};{g['cols']*g['cw']}t").encode()
        def observe(label,seq,expected):
            data=phase(label,seq,None);rec['observations'][label]={'wire':data.hex(),'expected':expected.hex()};rec['checks'][label]=(data==expected)
        def move(label,cols,rows,enabled,zoom=False):
            before=measure();phase('arm-'+label,'',b'')
            read_start=len(current()['resize_reads'])
            if zoom:u.SendMessageW(hwnd,0x111,0x0940,0) # Native Zoom In command, while subscribed
            else:
                r=w.RECT();assert u.GetWindowRect(outer,c.byref(r));assert u.SetWindowPos(outer,None,0,0,r.right-r.left+(cols-before['cols'])*before['cw'],r.bottom-r.top+(rows-before['rows'])*before['ch'],0x16)
            def ready():
                m=measure();return m if ((m['cw'],m['ch'])!=(before['cw'],before['ch']) if zoom else (m['cols'],m['rows'])==(cols,rows)) else None
            g=wait_for(ready);desk.chord(ord('9'))
            snapshot=wait_for(lambda:s if bytes.fromhex((s:=current())['hex']).endswith(b'9') else None)
            data=bytes.fromhex(snapshot['hex']);assert data.startswith(ACK)
            body=data[len(ACK):-1];matches=list(NOTICE.finditer(body));last=notice(g)
            valid=(matches and matches[-1].group()==last and b''.join(m.group() for m in matches)==body) if enabled else body==b''
            rec['checks'][label]=bool(valid);rec['observations'][label]={'geometry':g,'wire':data.hex(),'expected_last':last.hex() if enabled else ''}
            chunks=snapshot['resize_reads'][read_start:];joined=b''.join(bytes.fromhex(c['wire']) for c in chunks)
            # Locate the ReadFile call completing the final report, even when
            # split at any byte or delivered together with the keyboard fence.
            at=0;grid_at_report=None
            for chunk in chunks:
                at+=len(bytes.fromhex(chunk['wire']))
                if matches and at>=matches[-1].end():grid_at_report=chunk['grid'];break
            rec['observations'][label]['native_reads']=chunks
            rec['checks'][label+'-at-read']=(len(snapshot['resize_reads'])<512 and joined==body+b'9' and
                (grid_at_report==[g['cols'],g['rows']] if enabled else joined==b'9'))
            observe(label+'-metrics',CSI+'16t'+CSI+'18t',(CSI+f"6;{g['ch']};{g['cw']}t"+CSI+f"8;{g['rows']};{g['cols']}t").encode())
        try:
            g=measure();off=b'\x1b[?2048;2$y';on=b'\x1b[?2048;1$y'
            observe('initial',QUERY,off);observe('subscribe',ON+QUERY,notice(g)+on);observe('subscribe-again',ON,notice(g));move('grow',84,27,True);move('zoom',None,None,True,True)
            g=measure();observe('alternate',CSI+'?1049h'+QUERY+CSI+'?1049l'+QUERY,on*2)
            observe('unsubscribe',OFF+QUERY,off);move('unsubscribed',76,22,False);g=measure();observe('resubscribe',ON,notice(g));observe('reset','\x1bc'+QUERY,off);move('after-reset',78,24,False)
        finally:desk.restore()
    try:run(name,[],exercise=exercise,barrier=(CSI+'5n',ACK),profile={'NemoTabs':int(tabbed),'NemoRenderer':{'gdi':0,'directx':2}[renderer],'FontHeight':10,'WindowBorder':BORDER,'WarnOnClose':0,'LockSize':0},font=os.environ['NEMOTERM_TEST_FONT'],source_reference='Mode 2048 specification; independent Win32 client area and child console grid')
    except Exception:rec['error']=traceback.format_exc()
    rec['passed']='error' not in rec and len(rec['checks'])==19 and all(rec['checks'].values());(root/'research'/(name+'-result.json')).write_text(json.dumps(rec,indent=2),encoding='utf-8');return rec['passed']


if __name__=='__main__':
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    os.environ['NEMOTERM_TEST_RESIZE_READS']='1'
    cases=[trial(os.environ['RENDERER'],tabbed) for tabbed in (False,True)];raise SystemExit(not all(cases))
