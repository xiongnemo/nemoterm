"""Independent grid selections and Ctrl-drag rectangular copying and pixels."""
from native_test_utils import (root,c,w,u,hashlib,json,os,subprocess,sys,tempfile,
    Path,time,wait_for,find_window,read_snapshot,write_snapshot,wait_snapshot,capture)
from clipboard_test_utils import SavedClipboard,clipboard_text
from gpu_capture import OwnedGPUCapture
import argparse
import uuid
import winreg
parser=argparse.ArgumentParser()
parser.add_argument('--renderer',type=int,choices=(0,1,2),default=0)
args=parser.parse_args()
u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
profile='selection-'+uuid.uuid4().hex
keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:
    winreg.SetValueEx(key,'NemoRenderer',0,winreg.REG_DWORD,args.renderer)
    winreg.SetValueEx(key,'WarnOnClose',0,winreg.REG_DWORD,0)
exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),checks=[],rectangles=[],requested_renderer=args.renderer)
with tempfile.TemporaryDirectory(prefix='nemoterm-selection-') as temporary:
    report,control=(Path(temporary)/name for name in ('report','control'))
    process=subprocess.Popen([str(exe),'-load',profile,'--cols','80','--rows','24','-e',sys.executable,
        str(root/'tests/mouse_fixture.py'),str(report),str(control)],
        env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
    saved=None; session=None; script=None; gpu=None
    try:
        hwnd=wait_for(lambda:find_window(process.pid));wait_for(lambda:read_snapshot(report))
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
            # Desktop motion is outside this deterministic input fixture.
            # The queued message is ignored; synchronous actions below are not.
            assert u.PostMessageW(hwnd,0x200,0,(ch//2)<<16|(cw//2))
            # Synchronous messages deliberately share a short time interval;
            # only the changed coordinates distinguish these from multi-clicks.
            values=[select(0,0,2),select(2,2,4),select(5,0,7),select(0,2,1)]
            assert values==['ABC','234','FGH','01'],(mode,values)
            evidence['checks'].append(dict(mode=mode,selections=values))
            assert bytes.fromhex(read_snapshot(report)['hex'])==b'\x1b[0n',read_snapshot(report)
        time.sleep(.1);captured('selection-window.png')
        # Check the default shortcut on the rectangular local selection. This
        # injects keys only on our owned terminal's UI thread, then restores its
        # state. Clipboard backup/restore still surrounds the entire fixture.
        def copy_shortcut():
            global serial
            serial+=1
            before=u.GetClipboardSequenceNumber()
            script.exports_sync.key(dict(id=serial,key=67,scan=46,modifiers=[16,17,160,162]))
            assert u.PostMessageW(hwnd,0x8322,0,0)
            assert wait_for(lambda:script.exports_sync.result())==dict(id=serial)
            wait_for(lambda:u.GetClipboardSequenceNumber()!=before)
            assert not errors,errors
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
                    write_snapshot(control,dict(phase=name,sequence=sequence+'\x1b[5n'))
                    wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('phase')==name and bytes.fromhex(v.get('hex','')).endswith(b'\x1b[0n'))
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
                    assert bytes.fromhex(read_snapshot(report)['hex'])==b'\x1b[0n',read_snapshot(report)
                    evidence['rectangles'].append(dict(mode=mode,alternate=alternate,corner=corner,text=copied,pixels=True))
        (root/'research/selection-observed.json').write_text(json.dumps(evidence,indent=2))
        print('Rapid independent selections and 16 Ctrl rectangles, exact Unicode, shortcut/right-click copy and pixels passed')
    finally:
        (root/'research/selection-last-snapshot.json').write_text(json.dumps(read_snapshot(report)))
        if gpu:gpu.close()
        if script:script.unload()
        if session:session.detach()
        if saved:saved.restore()
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
        write_snapshot(control,dict(stop=True))
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5);raise
