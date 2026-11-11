"""OSC 52 policies, clipboard text and bounded queries through an owned HWND."""
import base64
import uuid
import winreg
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, threading, time, read_snapshot, write_snapshot,
    wait_for, wait_snapshot, find_window, capture, memory_sample)
from clipboard_test_utils import SavedClipboard, clipboard_text

LIMIT = 256*1024
MARKER = b'\x1b[?1000;2$y'
evidence, samples = {}, []
u.GetClientRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
u.SendMessageTimeoutW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM,w.UINT,w.UINT,c.POINTER(c.c_size_t)]

def bounded_clipboard_text(hwnd):
    wait_for(lambda:u.OpenClipboard(hwnd))
    try:
        memory=u.GetClipboardData(13)
        if not memory: return None
        size=min(k.GlobalSize(memory),2*(LIMIT+1)) & ~1
        pointer=k.GlobalLock(memory)
        if not pointer: return None
        try:
            text=c.string_at(pointer,size).decode('utf-16-le',errors='replace')
            return text.split('\0',1)[0] if '\0' in text else None
        finally:
            k.GlobalUnlock(memory)
    finally:
        u.CloseClipboard()

def osc(target, text, end='\x1b\\'):
    return '\x1b]52;'+target+';'+base64.b64encode(text.encode()).decode()+end

def reply(target, text, end='\x1b\\'):
    return osc(target,text,end).encode()

def put_clipboard(hwnd, text, terminate=True, expected_owner=None):
    raw = text.encode('utf-16-le')+(b'\0\0' if terminate else b'')
    memory = k.GlobalAlloc(2,len(raw))
    assert memory
    pointer = k.GlobalLock(memory)
    assert pointer
    if not terminate:
        # Fill all allocator-rounded bytes so the malformed string has no NUL.
        c.memset(pointer,65,k.GlobalSize(memory))
    else:
        c.memmove(pointer,raw,len(raw))
    k.GlobalUnlock(memory)
    wait_for(lambda:u.OpenClipboard(hwnd))
    try:
        if expected_owner is not None and u.GetClipboardOwner()!=expected_owner:
            k.GlobalFree(memory)
            return
        assert u.EmptyClipboard()
        assert u.SetClipboardData(13,memory)
    finally:
        u.CloseClipboard()

def run_case(name, settings):
    with tempfile.TemporaryDirectory(prefix='nemoterm-osc52-') as directory:
        directory=Path(directory)
        report,control=directory/'report.json',directory/'control.json'
        profile='osc52-'+uuid.uuid4().hex
        profile_path='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,profile_path) as key:
            for setting,value in dict(WarnOnClose=0,**settings).items():
                winreg.SetValueEx(key,setting,0,winreg.REG_DWORD,value)
        process=subprocess.Popen([str(root/'dist/nemoterm.exe'),'-load',profile,
            '--cols','80','--rows','24','-e',sys.executable,str(root/'tests/mouse_fixture.py'),
            str(report),str(control)],env=dict(os.environ,NEMOTERM_CONPTY='bundled'),
            creationflags=subprocess.CREATE_NO_WINDOW)
        handle=k.OpenProcess(0x410,False,process.pid)
        stop=threading.Event(); saved=None; counter=0
        def sampler():
            while not stop.is_set():
                samples.append(memory_sample(handle)); stop.wait(.025)
        worker=threading.Thread(target=sampler,daemon=True); worker.start()
        def current():
            value=read_snapshot(report)
            assert not value.get('error') and process.poll() is None,value
            return value
        def phase(label,sequence,expected=b'',clipboard=None,quiet=False):
            nonlocal counter
            counter+=1; label=f'{name}-{counter}-{label}'
            write_snapshot(control,{'phase':label,'sequence':sequence+'\x1b[?1000$p'})
            def matches(value):
                data=bytes.fromhex(value.get('hex',''))
                return value.get('phase')==label and data.count(MARKER)==1 and data.replace(MARKER,b'',1)==expected
            try:
                value=wait_snapshot(current,matches)
                time.sleep(.25 if quiet else .05)
                value=wait_snapshot(current,lambda v:v.get('phase')==label)
                assert matches(value),(label,expected.hex(),value)
                if clipboard is not None:
                    wait_for(lambda:clipboard_text(hwnd)==clipboard)
            except AssertionError:
                raise AssertionError((label,expected[:80].hex(),current(),repr(bounded_clipboard_text(hwnd))[:120]))
            # Keep large replies compact but check every byte before hashing.
            evidence[label]={'input_bytes':len(sequence.encode()),'reply_bytes':len(expected),
                             'reply_sha256':hashlib.sha256(expected).hexdigest()}
            return value
        try:
            hwnd=wait_for(lambda:find_window(process.pid)); wait_for(current)
            saved=SavedClipboard(hwnd)
            put_clipboard(hwnd,'ORIGINAL secret '+name)
            phase('setup','\x1b[?25l\x1b[2J\x1b[1;1HOSC52 LOCAL SELECTION')
            if name=='default':
                phase('unicode-copy',osc('c','中文 😀\r\nline\ttab'),clipboard='中文 😀\r\nline\ttab')
                phase('read-denied','\x1b]52;c;?\x07',clipboard='中文 😀\r\nline\ttab',quiet=True)
                phase('clear','\x1b]52;c;!\x07',clipboard='')
            elif name=='disabled':
                original='ORIGINAL secret '+name
                phase('write-clear-read-denied',osc('c','replacement')+'\x1b]52;c;!\x07\x1b]52;c;?\x07',
                      clipboard=original,quiet=True)
            elif name=='read-only':
                original='ORIGINAL secret '+name
                phase('read-only',osc('c','replacement')+'\x1b]52;c;?\x07',reply('c',original,'\x07'),original)
            else:
                # Select the label locally; copying remotely to c must preserve it.
                rect=w.RECT(); u.GetClientRect(hwnd,c.byref(rect))
                cw,ch=(rect.right-2)//80,(rect.bottom-2)//24
                start=(1+ch//2)<<16 | (1+cw//2)
                end=(1+ch//2)<<16 | (1+20*cw+cw//2)
                u.SendMessageW(hwnd,0x201,5,start); u.SendMessageW(hwnd,0x200,5,end)
                u.SendMessageW(hwnd,0x202,4,end)
                phase('local-primary','\x1b]52;p;?\x07',reply('p','OSC52 LOCAL SELECTION','\x07'))
                selected=capture(hwnd,return_pixels=True)
                phase('copy-preserves-primary',osc('c','remote 系统 😀')+'\x1b]52;p;?\x07',
                      reply('p','OSC52 LOCAL SELECTION','\x07'),'remote 系统 😀')
                assert capture(hwnd,return_pixels=True)==selected,'system copy changed local selection pixels'
                phase('read-unicode','\x1b]52;c;?\x1b\\',reply('c','remote 系统 😀'))
                frozen=capture(hwnd,return_pixels=True)
                phase('synchronized-read','\x1b[?2026h\x1b[1;1HHIDDEN '+osc('c','remote 系统 😀')+
                      '\x1b]52;c;?\x07',reply('c','remote 系统 😀','\x07'),'remote 系统 😀')
                assert capture(hwnd,return_pixels=True)==frozen,'OSC 52 ended synchronized presentation'
                phase('synchronized-release','\x1b[?2026l')
                phase('primary-secondary',osc('p','primary')+osc('q','secondary')+'\x1b]52;p;?\x07',
                      reply('p','primary','\x07'),'remote 系统 😀')
                phase('secondary','\x1b]52;q;?\x1b\\',reply('q','secondary'))
                phase('default-target',osc('','default target')+'\x1b]52;0;?\x07',
                      reply('0','default target','\x07'),'default target')
                phase('selection-alias','\x1b]52;s;?\x07',reply('c','default target','\x07'))
                phase('fallback',osc('7','cut seven')+'\x1b]52;q;!\x07\x1b]52;q7;?\x07',
                      reply('7','cut seven','\x07'))
                phase('cancel-and-invalid',osc('c','retained')+'\x1b]52;c;AA==\x07'
                      '\x1b]52;c;/w==\x07\x1b]52;x;Yg==\x07\x1b]52;c;Yg\x18',clipboard='retained')
                phase('malformed-clear','\x1b]52;c;YQ=\x07',clipboard='')
                text='bounded 界 😀\n'*(LIMIT//32)
                phase('large-unicode',osc('c',text)+'\x1b]52;c;?\x07',reply('c',text,'\x07'),text)
                exact='a'*LIMIT
                phase('exact-limit',osc('c',exact)+'\x1b]52;c;?\x07',reply('c',exact,'\x07'),exact)
                phase('over-limit',osc('c',exact+'a'),clipboard=exact)
                put_clipboard(hwnd,'b'*(LIMIT+1))
                phase('oversized-read','\x1b]52;c;?\x07',reply('c','','\x07'))
                put_clipboard(hwnd,'malformed',terminate=False)
                # Windows may copy and terminate CF_UNICODETEXT on publication.
                # Test the actual bounded format it exposes, not the input allocation.
                normalized=bounded_clipboard_text(hwnd)
                evidence['unterminated-publication']={'normalized_by_windows':normalized is not None}
                phase('bounded-format-read','\x1b]52;c;?\x07',reply('c',normalized or '','\x07'))
                put_clipboard(hwnd,'lock test')
                # OpenClipboard contention happens off the terminal UI thread.
                assert u.OpenClipboard(hwnd)
                try:
                    write_snapshot(control,{'phase':'read-lock','sequence':'\x1b]52;c;?\x07\x1b[?1000$p'})
                    wait_snapshot(current,lambda v:v.get('phase')=='read-lock' and MARKER in bytes.fromhex(v.get('hex','')))
                    assert u.MoveWindow(hwnd,30,30,760,530,True)
                    time.sleep(.18)
                finally:
                    u.CloseClipboard()
                value=wait_snapshot(current,lambda v:reply('c','','\x07') in bytes.fromhex(v.get('hex','')))
                evidence['read-lock']={'responsive_resize':value['columns']!=80}
                assert evidence['read-lock']['responsive_resize']
                phase('read-after-contention','\x1b]52;c;?\x07',reply('c','lock test','\x07'))
                for cancel in (False,True):
                    delayed_report=directory/f'delayed-{cancel}.json'
                    delayed_control=directory/f'delayed-{cancel}-control.json'
                    helper=subprocess.Popen([sys.executable,str(root/'tests/osc52_delayed_fixture.py'),
                        str(delayed_report),str(delayed_control)],creationflags=subprocess.CREATE_NO_WINDOW)
                    delayed_hwnd=None
                    try:
                        ready=wait_snapshot(lambda:read_snapshot(delayed_report),lambda v:v.get('state')=='ready')
                        delayed_hwnd=ready['hwnd']
                        label=f'delayed-read-{cancel}'
                        write_snapshot(control,{'phase':label,'sequence':'\x1b]52;c;?\x07\x1b[?1000$p'})
                        wait_snapshot(lambda:read_snapshot(delayed_report),lambda v:v.get('state')=='rendering')
                        response=c.c_size_t()
                        assert u.SendMessageTimeoutW(hwnd,0,0,0,2,300,c.byref(response)), 'UI blocked on delayed clipboard'
                        if cancel:
                            label='reset-during-delayed-read'
                            write_snapshot(control,{'phase':label,'sequence':'\x1bc\x1b[?25l\x1b[?1000$p'})
                            wait_snapshot(current,lambda v:v.get('phase')==label and bytes.fromhex(v.get('hex',''))==MARKER)
                        write_snapshot(delayed_control,{'release':True})
                        wait_snapshot(lambda:read_snapshot(delayed_report),lambda v:v.get('state')=='rendered')
                        expected=MARKER+(b'' if cancel else reply('c','delayed clipboard 秘密 😀','\x07'))
                        wait_snapshot(current,lambda v:v.get('phase')==label and bytes.fromhex(v.get('hex',''))==expected)
                        time.sleep(.2)
                        value=wait_snapshot(current,lambda v:v.get('phase')==label)
                        assert bytes.fromhex(value['hex'])==expected,value
                        evidence[label]={'ui_responsive':True,'reply_suppressed_after_reset':cancel}
                    finally:
                        write_snapshot(delayed_control,{'release':True})
                        # Reclaim only our test-owned data before SavedClipboard restores it.
                        if delayed_hwnd:
                            put_clipboard(hwnd,'lock test',expected_owner=delayed_hwnd)
                        write_snapshot(delayed_control,{'release':True,'stop':True})
                        helper.wait(timeout=8)
                # Avoid changing any real clipboard updates from another application.
                phase('reset-preserves-cut-buffer','\x1bc\x1b[?25l\x1b]52;7;?\x07',reply('7','cut seven','\x07'))
                phase('alternate-preserves-cut-buffer','\x1b[?1049h\x1b]52;7;?\x07\x1b[?1049l',
                      reply('7','cut seven','\x07'))
                for index in range(24):
                    phase('cache-pressure',osc(str(index%8),chr(65+index%26)*LIMIT))
                phase('cache-latest','\x1b]52;7;?\x07',reply('7','X'*LIMIT,'\x07'))
                phase('cache-evicted','\x1b]52;0;?\x07',reply('0','','\x07'))
                phase('shared-cache',osc('q01234567','shared')+'\x1b]52;q;?\x07',reply('q','shared','\x07'))
                phase('finished','\x1b[2J\x1b[1;1HOSC 52 clipboard regression passed\r\n'
                      'Policies / Unicode / local selection / bounded data / async read')
                capture(hwnd,'osc52-window.png')
        finally:
            if saved: saved.restore()
            stop.set(); worker.join(2); k.CloseHandle(handle)
            write_snapshot(control,{'stop':True})
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate(); process.wait(timeout=5)
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,profile_path)

for name,settings in [('default',{}),('disabled',{'NemoOSC52Write':0}),
                      ('read-only',{'NemoOSC52Read':1,'NemoOSC52Write':0}),
                      ('read-write',{'NemoOSC52Read':1})]:
    run_case(name,settings)
evidence.update(executable_sha256=hashlib.sha256((root/'dist/nemoterm.exe').read_bytes()).hexdigest(),
                peak_private_ws=max(s['private_ws'] for s in samples),
                peak_total_ws=max(s['total_ws'] for s in samples),
                peak_private_commit=max(s['private_commit'] for s in samples))
assert evidence['peak_private_ws']<20_000_000,evidence
(root/'research/osc52-window-observed.json').write_text(json.dumps(evidence,indent=2))
print('Native OSC 52 policies, clipboard and bounded memory passed:',evidence)
