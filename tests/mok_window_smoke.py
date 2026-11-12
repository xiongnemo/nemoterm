"""xterm character-key negotiation through an owned Win32 HWND and ConPTY."""
from native_test_utils import (root,c,w,u,k,hashlib,json,os,subprocess,sys,tempfile,
    Path,time,threading,read_snapshot,write_snapshot,wait_snapshot,memory_sample,
    wait_for,find_window,capture)
from clipboard_test_utils import SavedClipboard,clipboard_text
import argparse
import uuid
import winreg

parser=argparse.ArgumentParser(); parser.add_argument('--font')
parser.add_argument('--initial-level',type=int,choices=range(4),default=0)
parser.add_argument('--initial-format',type=int,choices=range(2),default=0)
options=parser.parse_args()
u.GetClientRect.argtypes = u.GetWindowRect.argtypes = [w.HWND,c.POINTER(w.RECT)]
with tempfile.TemporaryDirectory(prefix='nemoterm-mok-') as directory:
    directory=Path(directory); report,control=directory/'report.json',directory/'control.json'
    profile='mok-'+uuid.uuid4().hex; profile_path='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,profile_path) as config:
        for name,value in dict(WarnOnClose=0,NemoModifyOtherKeys=options.initial_level,
                               NemoFormatOtherKeys=options.initial_format,
                               AltSpace=0,FullScreenOnAltEnter=0).items():
            winreg.SetValueEx(config,name,0,winreg.REG_DWORD,value)
    process=subprocess.Popen([str(root/'dist/nemoterm.exe'),'-load',profile,'--cols','80','--rows','24',
        *(['--font',options.font] if options.font else []),'-e',sys.executable,
        str(root/'tests/mouse_fixture.py'),str(report),str(control)],
        env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
    handle=k.OpenProcess(0x410,False,process.pid)
    evidence,samples,saved={},[],None
    stop=threading.Event()
    def sample():
        while not stop.is_set():
            samples.append(memory_sample(handle)); stop.wait(.025)
    worker=threading.Thread(target=sample,daemon=True); worker.start()
    expected,phase_name=b'',''
    def current():
        value=read_snapshot(report)
        assert not value.get('error') and process.poll() is None,value
        return value
    def check():
        try:
            wait_snapshot(current,lambda v:v.get('phase')==phase_name and bytes.fromhex(v.get('hex',''))==expected)
            time.sleep(.06)
            value=wait_snapshot(current,lambda v:v.get('phase')==phase_name)
            assert bytes.fromhex(value['hex'])==expected
        except AssertionError:
            raise AssertionError((phase_name,expected.hex(),current()))
        evidence[phase_name]=value
    def phase(name,sequence,reply):
        global expected,phase_name
        expected,phase_name=reply,name
        write_snapshot(control,{'phase':name,'sequence':sequence}); check()
    def key(vk,scan,event=1,count=1,system=False):
        lp=count | ((scan&511)<<16)
        if event!=1: lp|=0x40000000
        if event==3: lp|=0x80000000
        if system: lp|=0x20000000
        u.SendMessageW(hwnd,(0x104 if system else 0x100)+(event==3),vk,lp)
    def chord(vk,scan,mods=0,repeat=1):
        held=[(bit,v,s) for bit,v,s in [(4,17,29),(1,16,42),(2,18,56)] if mods&bit]
        for bit,v,s in held: key(v,s,system=bit==2)
        key(vk,scan,count=repeat,system=bool(mods&2)); key(vk,scan,3,system=bool(mods&2))
        for bit,v,s in reversed(held): key(v,s,3,system=bit==2)
    def code(keycode,mods=0,fmt=0):
        return (f'\x1b[{keycode};{mods+1}u' if fmt else f'\x1b[27;{mods+1};{keycode}~').encode()
    try:
        hwnd=wait_for(lambda:find_window(process.pid)); wait_for(current)
        initial_reply=f'\x1b[>4;{options.initial_level}m\x1b[>4;{options.initial_format}f'.encode()
        phase('initial','\x1b[?4m\x1b[?4g',initial_reply)
        if options.initial_level==3:
            chord(65,30)
            expected+=code(65 if u.GetKeyState(20)&1 else 97,0,options.initial_format); check()
        rect=w.RECT(); u.GetClientRect(hwnd,c.byref(rect))
        cw,ch=(rect.right-2)//80,(rect.bottom-2)//24
        phase('level-one','\x1b[>4;0f\x1b[>4;1m\x1b[?4m',b'\x1b[>4;1m')
        for vk,scan in [(16,42),(16,54),(17,29),(17,285),(18,56),(18,312),(91,347),(92,348)]: key(vk,scan,3)
        caps=bool(u.GetKeyState(20)&1); letter=65 if caps else 97; shifted=97 if caps else 65
        chord(65,30,4); expected+=b'\x01'
        chord(190,52,4); expected+=code(46,4)
        chord(190,52,6); expected+=code(46,4)
        chord(9,15,1); expected+=b'\x1b[Z'
        chord(9,15,4); expected+=code(9,4)
        chord(13,28,1); expected+=code(13,1)
        chord(65,30,2); expected+=b'\x1b'+bytes([letter])
        check()
        phase('level-two','\x1b[>4;2m\x1b[?4m',b'\x1b[>4;2m')
        for vk,scan,mods,value in [(65,30,1,shifted),(65,30,4,letter),(65,30,5,shifted),
                                   (65,30,2,letter),(49,2,5,33),(9,15,1,9),(9,15,5,9),
                                   (9,15,2,9),(13,28,2,13),(8,14,1,127),(27,1,4,27)]:
            chord(vk,scan,mods); expected+=code(value,mods)
        chord(49,2,1); expected+=b'!'
        chord(65,30,4,repeat=3); expected+=3*code(letter,4)
        chord(38,328); expected+=b'\x1b[A'
        chord(112,59); expected+=b'\x1bOP'
        check()
        phase('format-and-mask','\x1b[>4;1f\x1b[>4;2:1m\x1b[?4g\x1bP$q>4m\x1b\\',
              b'\x1b[>4;1f\x1bP1$r>4;2:1m\x1b\\')
        chord(65,30,5); expected+=code(letter,5,1)
        chord(49,2,5); expected+=code(49,5,1)
        check()
        phase('all-keys','\x1b[>4;3m\x1b[?4m',b'\x1b[>4;3m')
        chord(65,30); expected+=code(letter,0,1)
        chord(13,28); expected+=code(13,0,1)
        chord(27,1); expected+=code(27,0,1)
        for scalar in (0x4e2d,0xd83d,0xde00,0xdc00): u.SendMessageW(hwnd,0x102,scalar,1)
        u.SendMessageW(hwnd,0x286,0x6587,1)
        expected+=code(20013,0,1)+code(128512,0,1)+code(25991,0,1)
        check()
        phase('shared-screen-state','\x1b[?1049h\x1b[?4m\x1b[>4;2m\x1b[?1049l\x1b[?4m',
              b'\x1b[>4;3m\x1b[>4;2m')
        phase('kitty-priority','\x1b[>4;3m\x1b[>1u\x1b[?u',b'\x1b[?1u')
        locks=(64 if caps else 0)|(128 if u.GetKeyState(144)&1 else 0)
        chord(73,23,4); expected+=f'\x1b[105;{locks+5}u'.encode(); check()
        phase('restore-xterm','\x1b[<u\x1b[?u\x1b[?4m',b'\x1b[?0u\x1b[>4;3m')
        chord(65,30); expected+=code(letter,0,1); check()
        phase('synchronized-input','\x1b[?2026h\x1b[?4m',b'\x1b[>4;3m')
        chord(65,30); expected+=code(letter,0,1); check()
        phase('focus-cleanup','\x1b[?2026l\x1b[?4m',b'\x1b[>4;3m')
        key(65,30); u.SendMessageW(hwnd,8,0,0); key(65,30,3)
        expected+=code(letter,0,1); check()
        phase('resize-preserves','\x1b[?4m',b'\x1b[>4;3m')
        bounds=w.RECT(); u.GetWindowRect(hwnd,c.byref(bounds))
        assert u.MoveWindow(hwnd,30,30,bounds.right-bounds.left-12*cw,bounds.bottom-bounds.top,True)
        wait_snapshot(current,lambda v:v.get('columns',80)<80)
        chord(65,30); expected+=code(letter,0,1); check()
        label='MOK COPY LABEL'
        phase('local-copy-paste','\x1b[2J\x1b[1;1H'+label+'\x1b[?1000;1006;2004h\x1b[?4m',b'\x1b[>4;3m')
        saved=SavedClipboard(hwnd)
        rect=w.RECT(); u.GetClientRect(hwnd,c.byref(rect)); size=current()
        left=(rect.right-size['columns']*cw)//2; top=(rect.bottom-size['rows']*ch)//2
        start=(top+ch//2)<<16 | (left+cw//2)
        end=(top+ch//2)<<16 | (left+(len(label)-1)*cw+cw//2)
        u.SendMessageW(hwnd,0x201,5,start); u.SendMessageW(hwnd,0x200,5,end); u.SendMessageW(hwnd,0x202,4,end)
        chord(67,46,5); assert wait_for(lambda:clipboard_text(hwnd))==label
        chord(86,47,5); expected+=b'\x1b[200~'+label.encode()+b'\x1b[201~'; check()
        saved.restore(); saved=None
        phase('bounded-mode-burst',('\x1b[>4;1m\x1b[>4;3:1m\x1b[>4;2:4m'*2000)+
              '\x1b[>4;3m\x1b[?4m',b'\x1b[>4;3m')
        phase('disabled','\x1b[>4n\x1b[?4m',b'\x1b[>4;65535m')
        chord(27,1); expected+=b'\x1b'; check()
        phase('reset-defaults','\x1bc\x1b[?25l\x1b[?4m\x1b[?4g',initial_reply)
        write_snapshot(control,{'phase':'finished','sequence':'modifyOtherKeys regression passed\r\n'
            'Levels / formats / Unicode / clipboard / mouse / resize'})
        wait_snapshot(current,lambda v:v.get('phase')=='finished'); time.sleep(.1)
        capture(hwnd,'mok-window.png')
        evidence.update(font=options.font or 'default',initial_level=options.initial_level,
            initial_format=options.initial_format,
            executable_sha256=hashlib.sha256((root/'dist/nemoterm.exe').read_bytes()).hexdigest(),
            peak_private_ws=max(s['private_ws'] for s in samples),
            peak_total_ws=max(s['total_ws'] for s in samples),
            peak_private_commit=max(s['private_commit'] for s in samples))
        assert evidence['peak_private_ws']<20_000_000,evidence
        (root/'research/mok-window-observed.json').write_text(json.dumps(evidence,indent=2))
        print('Native modifyOtherKeys passed:',evidence)
    finally:
        if saved: saved.restore()
        stop.set(); worker.join(2); k.CloseHandle(handle)
        write_snapshot(control,{'stop':True})
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.terminate(); process.wait(timeout=5)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,profile_path)
