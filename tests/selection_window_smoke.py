"""Rapid selections at different coordinates retain character-grid granularity."""
from native_test_utils import (root,c,w,u,hashlib,json,os,subprocess,sys,tempfile,
    Path,time,wait_for,find_window,read_snapshot,write_snapshot,wait_snapshot,capture)
from clipboard_test_utils import SavedClipboard,clipboard_text
exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),checks=[])
with tempfile.TemporaryDirectory(prefix='nemoterm-selection-') as temporary:
    report,control=(Path(temporary)/name for name in ('report','control'))
    process=subprocess.Popen([str(exe),'--cols','80','--rows','24','-e',sys.executable,
        str(root/'tests/mouse_fixture.py'),str(report),str(control)],
        env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
    saved=None
    try:
        hwnd=wait_for(lambda:find_window(process.pid));wait_for(lambda:read_snapshot(report))
        saved=SavedClipboard(hwnd)
        r=w.RECT();u.GetClientRect(hwnd,c.byref(r));cw,ch=(r.right-2)//80,(r.bottom-2)//24
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
            write_snapshot(control,dict(phase=mode,sequence=sequence+'\x1b[5n'))
            wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('phase')==mode and bytes.fromhex(v.get('hex','')).endswith(b'\x1b[0n'))
            # Synchronous messages deliberately share a short time interval;
            # only the changed coordinates distinguish these from multi-clicks.
            values=[select(0,0,2),select(2,2,4),select(5,0,7),select(0,2,1)]
            assert values==['ABC','234','FGH','01'],(mode,values)
            evidence['checks'].append(dict(mode=mode,selections=values))
            assert bytes.fromhex(read_snapshot(report)['hex'])==b'\x1b[0n',read_snapshot(report)
        time.sleep(.1);capture(hwnd,'selection-window.png')
        (root/'research/selection-observed.json').write_text(json.dumps(evidence,indent=2))
        print('Rapid independent grid selections and right-click copy passed')
    finally:
        if saved:saved.restore()
        write_snapshot(control,dict(stop=True))
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5);raise
