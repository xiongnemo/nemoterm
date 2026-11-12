"""Check native console records and VT bytes through our own HWND and ConPTY.

SendMessage only: no global input, focus or keyboard-layout changes.
"""
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, time, read_snapshot, write_snapshot, wait_snapshot,
    memory_sample, wait_for, find_window, capture)
from clipboard_test_utils import SavedClipboard, clipboard_text
import uuid
import winreg

u.GetWindowTextW.argtypes=[w.HWND,w.LPWSTR,c.c_int]

evidence, samples = {}, []
for vt in (False, True):
    with tempfile.TemporaryDirectory(prefix='nemoterm-win32-') as directory:
        report, control = (Path(directory)/name for name in ('report.json','control.json'))
        profile='win32-'+uuid.uuid4().hex
        profile_path='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,profile_path) as config:
            for name,value in dict(NemoWin32Input=1,WarnOnClose=0).items():
                winreg.SetValueEx(config,name,0,winreg.REG_DWORD,value)
        process = subprocess.Popen([str(root/'dist/nemoterm.exe'), '-load',profile,'--cols','80','--rows','24',
            '-e',sys.executable,str(root/'tests/win32_input_fixture.py'),str(report),str(control),
            *(['--vt'] if vt else [])], env=dict(os.environ,NEMOTERM_CONPTY='bundled'),
            creationflags=subprocess.CREATE_NO_WINDOW)
        handle = k.OpenProcess(0x410,False,process.pid)
        saved = None
        prefix = 'vt-' if vt else 'console-'
        phase_name = ''

        def current():
            value = wait_snapshot(lambda: read_snapshot(report))
            assert not value.get('error') and process.poll() is None, value
            return value

        def title():
            value = c.create_unicode_buffer(256)
            u.GetWindowTextW(hwnd,value,len(value))
            return value.value

        def phase(name, sequence='', processed=False):
            global phase_name
            phase_name = prefix+name
            write_snapshot(control,dict(phase=phase_name,sequence=sequence,processed=processed))
            wait_for(lambda: phase_name in title())
            wait_snapshot(current,lambda v:v.get('phase')==phase_name)

        def key(vk,scan,down=True,repeat=1,again=False):
            lp = repeat | ((scan&255)<<16) | ((scan&256)<<16)
            if again or not down: lp |= 0x40000000
            if not down: lp |= 0x80000000
            u.SendMessageW(hwnd,0x100 if down else 0x101,vk,lp)

        def tap(vk,scan):
            key(vk,scan);key(vk,scan,False)

        def record(vk,scan,ch=0,down=True,control=0,repeat=1):
            return dict(type='key',vk=vk,scan=scan&255,character=ch,down=int(down),
                        control=locks|control|(256 if scan&256 else 0),repeat=repeat)

        def records(expected):
            def keys(v): return [e for e in v.get('events',[]) if e['type']=='key']
            try:
                wait_snapshot(current,lambda v:keys(v)==expected)
                time.sleep(.08)
                result=current()
                assert keys(result)==expected
            except AssertionError:
                raise AssertionError((phase_name,expected,current()))
            evidence[phase_name]=result
            samples.append(memory_sample(handle))

        def bytes_equal(expected):
            try:
                wait_snapshot(current,lambda v:bytes.fromhex(v.get('hex',''))==expected)
                time.sleep(.08)
                result=current()
                assert bytes.fromhex(result['hex'])==expected
            except AssertionError:
                raise AssertionError((phase_name,expected.hex(),current()))
            evidence[phase_name]=result
            samples.append(memory_sample(handle))

        try:
            hwnd=wait_for(lambda:find_window(process.pid))
            wait_for(current)
            phase('ready')
            for vk,scan in [(16,42),(16,54),(17,29),(17,285),(18,56),(18,312),(91,347),(92,348)]:
                key(vk,scan,False)
            locks = (128 if u.GetKeyState(20)&1 else 0)|(32 if u.GetKeyState(144)&1 else 0)|(64 if u.GetKeyState(145)&1 else 0)
            a = 65 if locks&128 else 97
            if not vt:
                # ConPTY requests 9001 by itself before the child starts. No
                # application negotiation here: raw records prove transport.
                phase('repeat-and-release')
                key(65,30,repeat=3);key(65,30,False)
                records([record(65,30,a,repeat=3),record(65,30,a,False)])
                phase('modifiers-and-distinct-keys')
                expected=[]
                for modifier,scan,mask,vk,vscan,ch in [
                    (16,42,16,13,28,13),(17,29,8,32,57,32),
                    (17,285,4,67,46,3),(18,56,2,65,30,a),
                    (18,312,1,112,59,0)]:
                    key(modifier,scan);tap(vk,vscan);key(modifier,scan,False)
                    expected += [record(modifier,scan,control=mask),record(vk,vscan,ch,control=mask),
                                 record(vk,vscan,ch,False,mask),record(modifier,scan,down=False)]
                tap(13,284);tap(38,328);tap(112,59);tap(135,118)
                expected += [record(vk,scan,ch,down) for vk,scan,ch in [(13,284,13),(38,328,0),(112,59,0),(135,118,0)] for down in (True,False)]
                records(expected)
                phase('unicode-commit')
                for unit in (0x4e2d,0xd83d,0xde00): u.SendMessageW(hwnd,0x102,unit,1)
                u.SendMessageW(hwnd,0x286,0x6587,1)
                records([dict(type='key',vk=0,scan=0,character=unit,down=1,control=0,repeat=1)
                         for unit in (0x4e2d,0xd83d,0xde00,0x6587)])
                phase('mouse-coexistence')
                rect=w.RECT();u.GetClientRect(hwnd,c.byref(rect))
                cw,ch=(rect.right-2)//80,(rect.bottom-2)//24
                point=(1+3*ch+ch//2)<<16|(1+2*cw+cw//2)
                u.SendMessageW(hwnd,0x201,1,point);u.SendMessageW(hwnd,0x202,0,point)
                expected_mouse=[dict(type='mouse',x=2,y=3,buttons=buttons,control=0,flags=0) for buttons in (1,0)]
                # Releasing capture can enqueue a move at the real pointer's
                # position. Check both button records exactly, retaining those
                # independent move records in the evidence for diagnosis.
                result=wait_snapshot(current,lambda v:[e for e in v['events']
                    if e['type']=='mouse' and e['flags']!=1]==expected_mouse)
                evidence[phase_name]=result
                phase('focus-release')
                key(65,30);u.SendMessageW(hwnd,8,0,0);key(65,30,False)
                records([record(65,30,a),record(65,30,a,False)])
                phase('processed-ctrl-c',processed=True)
                key(17,29);tap(67,46);key(17,29,False)
                wait_snapshot(current,lambda v:0 in v['signals'])
                evidence[phase_name]=current()
                phase('processed-ctrl-break',processed=True)
                key(17,29);tap(3,326);key(17,29,False)
                wait_snapshot(current,lambda v:1 in v['signals'])
                evidence[phase_name]=current()
                phase('resize')
                before=current()['columns']
                assert u.MoveWindow(hwnd,30,30,700,500,True)
                result=wait_snapshot(current,lambda v:v['columns']!=before and
                    any(e['type']=='resize' and (e['columns'],e['rows'])==(v['columns'],v['rows']) for e in v['events']))
                evidence[phase_name]=result
                # Window size notifications and native key records coexist.
                tap(13,284)
                records([record(13,284,13),record(13,284,13,False)])
            else:
                phase('legacy','\x1b[?9001l')
                tap(65,30);tap(38,328);tap(13,28)
                bytes_equal(bytes([a])+b'\x1b[A\r')
                # The pinned ConPTY does not re-encode raw F24 into legacy VT.
                # Keep this measured limitation explicit; default-off policy
                # preserves the existing direct VT path tested by query suite.
                phase('conpty-f24-limitation')
                tap(135,118);bytes_equal(b'')
                phase('application-win32','\x1b[?9001h')
                key(65,30,repeat=3);key(65,30,False)
                def encoded(e):
                    return ('\x1b[%d;%d;%d;%d;%d;%d_'%(e['vk'],e['scan'],e['character'],e['down'],e['control'],e['repeat'])).encode()
                bytes_equal(encoded(record(65,30,a,repeat=3))+encoded(record(65,30,a,False)))
                phase('kitty-priority','\x1b[?9001l\x1b[=3u')
                tap(27,1)
                mods=(64 if locks&128 else 0)|(128 if locks&32 else 0)
                bytes_equal(f'\x1b[27;{mods+1}u\x1b[27;{mods+1}:3u'.encode())
                phase('mok-priority','\x1b[=0u\x1b[>4;3m')
                tap(65,30)
                bytes_equal(f'\x1b[27;1;{a}~'.encode())
                phase('legacy-restored','\x1b[>4;0m')
                tap(65,30);bytes_equal(bytes([a]))
                phase('local-copy-paste','\x1b[2J\x1b[HWIN32 COPY LABEL\x1b[?1000;1006;2004h')
                saved=SavedClipboard(hwnd)
                rect=w.RECT();u.GetClientRect(hwnd,c.byref(rect))
                cw,ch=(rect.right-2)//80,(rect.bottom-2)//24
                start=(1+ch//2)<<16|(1+cw//2)
                end=(1+ch//2)<<16|(1+15*cw+cw//2)
                u.SendMessageW(hwnd,0x201,5,start);u.SendMessageW(hwnd,0x200,5,end);u.SendMessageW(hwnd,0x202,4,end)
                key(17,29);key(16,42);tap(67,46)
                copied=wait_for(lambda:clipboard_text(hwnd))
                assert copied=='WIN32 COPY LABEL',repr(copied)
                tap(86,47);key(16,42,False);key(17,29,False)
                bytes_equal(b'\x1b[200~WIN32 COPY LABEL\x1b[201~')
                saved.restore();saved=None
                phase('complete','\x1b[?1000;1006;2004l\x1b[2J\x1b[HWin32 input regression passed\r\nConsole records / VT / Unicode / resize / copy-paste\r\n')
                capture(hwnd,'win32-input-window.png')
        except Exception as error:
            evidence.update(failure=repr(error),failed_phase=phase_name,
                failed_snapshot=read_snapshot(report),
                executable_sha256=hashlib.sha256((root/'dist/nemoterm.exe').read_bytes()).hexdigest())
            (root/'research/win32-input-observed.json').write_text(json.dumps(evidence,indent=2))
            print('Win32 failure snapshot:',evidence['failed_snapshot'])
            raise
        finally:
            if saved:saved.restore()
            k.CloseHandle(handle)
            write_snapshot(control,dict(stop=True))
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate();process.wait(timeout=5)
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,profile_path)

evidence.update(executable_sha256=hashlib.sha256((root/'dist/nemoterm.exe').read_bytes()).hexdigest(),
    peak_private_ws=max(s['private_ws'] for s in samples),peak_total_ws=max(s['total_ws'] for s in samples),
    peak_private_commit=max(s['private_commit'] for s in samples))
assert evidence['peak_private_ws']<20_000_000,evidence
(root/'research/win32-input-observed.json').write_text(json.dumps(evidence,indent=2))
print('Native Win32 input passed:',{k:v for k,v in evidence.items() if k.startswith(('peak_','executable_'))})
