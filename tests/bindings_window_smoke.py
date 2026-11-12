"""Saved custom bindings exercised through the owned window's input thread."""
from native_test_utils import *
from clipboard_test_utils import SavedClipboard,clipboard_text
import uuid,winreg,frida

exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
profile='bindings-test-'+uuid.uuid4().hex
path='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
with winreg.CreateKey(winreg.HKEY_CURRENT_USER,path) as key:
    for name,value in dict(NemoCopyBinding=0x658,NemoPasteBinding=0x559,
                          NemoCopyPasteBinding=0x35a,NemoRectangleModifiers=4,WarnOnClose=0).items():
        winreg.SetValueEx(key,name,0,winreg.REG_DWORD,value)
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),checks=[])
try:
    with tempfile.TemporaryDirectory(prefix='nemoterm-bindings-') as tmp:
        report,control=(Path(tmp)/n for n in ('report','control'))
        process=subprocess.Popen([str(exe),'-load',profile,'--cols','80','--rows','24','-e',
            sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control)],
            env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_UTF8_INPUT='1'),creationflags=subprocess.CREATE_NO_WINDOW)
        saved=session=script=None
        try:
            hwnd=wait_for(lambda:find_window(process.pid));wait_for(lambda:read_snapshot(report))
            saved=SavedClipboard(hwnd);session=frida.attach(process.pid)
            script=session.create_script((root/'tests/agent_key_probe.js').read_text());script.load();serial=0
            def action(**op):
                global serial
                serial+=1;script.exports_sync.key(dict(id=serial,**op))
                assert u.PostMessageW(hwnd,0x8322,0,0)
                assert wait_for(lambda:script.exports_sync.result())==dict(id=serial)
            def phase(name,text):
                write_snapshot(control,dict(phase=name,sequence=text+'\x1b[5n'))
                wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('phase')==name and v.get('hex')=='1b5b306e')
            r=w.RECT();u.GetClientRect(hwnd,c.byref(r));cw,ch=(r.right-2)//80,(r.bottom-2)//24
            def point(x,y):return (1+y*ch+ch//2)<<16|(1+x*cw+cw//2)
            for appmouse in (False,True):
                phase('alt-rectangle-'+str(appmouse),'\x1b[?25l\x1b[2J\x1b[H0123456789\r\nab中e\u0301FGHIJ\r\nklmnopqrst'+('\x1b[?1003;1006h' if appmouse else ''))
                mods=[18,164]+([16,160] if appmouse else [])
                action(modifiers=mods,mouse=[dict(message=0x201,keys=5 if appmouse else 1,point=point(1,0)),
                    dict(message=0x200,keys=5 if appmouse else 1,point=point(5,2)),dict(message=0x202,keys=4 if appmouse else 0,point=point(5,2))])
                before=u.GetClipboardSequenceNumber()
                action(key=88,scan=45,modifiers=[17,18,162,164])
                wait_for(lambda:u.GetClipboardSequenceNumber()!=before)
                expected='12345\r\nb中e\u0301F\r\nlmnop'
                assert clipboard_text(hwnd)==expected
                assert read_snapshot(report)['hex']=='1b5b306e'
                evidence['checks'].append(dict(action='Alt rectangle and Ctrl+Alt+X copy',application_mouse=appmouse,text=expected))
            # Copy/paste action uses exactly this selection, including Unicode.
            action(key=90,scan=44,modifiers=[16,17,160,162])
            expected_input=b'\x1b[0n'+expected.replace('\r\n','\r').encode()
            wait_snapshot(lambda:read_snapshot(report),lambda v:bytes.fromhex(v.get('hex',''))==expected_input)
            evidence['checks'].append(dict(action='Ctrl+Shift+Z copy and paste',hex=expected_input.hex()))
            phase('paste','\x1b[?2004h')
            action(key=89,scan=21,modifiers=[16,18,160,164])
            expected_input=b'\x1b[0n\x1b[200~'+expected.replace('\r\n','\r').encode()+b'\x1b[201~'
            wait_snapshot(lambda:read_snapshot(report),lambda v:bytes.fromhex(v.get('hex',''))==expected_input)
            evidence['checks'].append(dict(action='Alt+Shift+Y bracketed paste',hex=expected_input.hex()))
            phase('unbound-default','\x1b[?2004l')
            action(key=67,scan=46,modifiers=[16,17,160,162])
            action(key=86,scan=47,modifiers=[16,17,160,162])
            wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('hex')=='1b5b306e0316')
            evidence['checks'].append(dict(action='Old shortcuts forwarded to child',hex='0316'))
        finally:
            (root/'research/bindings-last-snapshot.json').write_text(json.dumps(read_snapshot(report)))
            if script:script.unload()
            if session:session.detach()
            if saved:saved.restore()
            write_snapshot(control,dict(stop=True))
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
finally:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,path)
(root/'research/bindings-observed.json').write_text(json.dumps(evidence,indent=2))
print('Custom copy/paste, Alt rectangles, application override and unbound key forwarding passed')
