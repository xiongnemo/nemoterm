"""Protected text, selective Sixel erasure, resize and clipboard through ConPTY."""
from native_test_utils import (root, c, w, u, k, hashlib, json, os, subprocess,
    sys, tempfile, Path, threading, time, read_snapshot, write_snapshot,
    wait_snapshot, memory_sample, wait_for, find_window, capture)
from clipboard_test_utils import SavedClipboard, clipboard_text

MARKER=b'\x1bP0$r\x1b\\'
executable=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe'))
CLEAR='\x1b[0"q\x1b[0m\x1b[?25l\x1b[r\x1b[2J\x1b[3J\x1b[H'
with tempfile.TemporaryDirectory(prefix='nemoterm-selective-') as directory:
    directory=Path(directory)
    report,control=directory/'report.json',directory/'control.json'
    process=subprocess.Popen([str(executable),'--cols','40','--rows','12',
        '-e',sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control)],
        env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
    handle=k.OpenProcess(0x410,False,process.pid)
    samples,errors,evidence=[],[],{}
    done,saved=threading.Event(),None
    def sample():
        while not done.is_set():
            try:samples.append(memory_sample(handle))
            except Exception as error:errors.append(repr(error));return
            done.wait(.025)
    worker=threading.Thread(target=sample);worker.start()
    def current():
        value=wait_snapshot(lambda:read_snapshot(report))
        assert process.poll() is None and not value.get('error'),value
        return value
    def phase(name,sequence,expected=b''):
        write_snapshot(control,dict(phase=name,preserve_mouse=True,
            sequence=sequence+'\x1bP$qerase-marker\x1b\\'))
        try:
            value=wait_snapshot(current,lambda v:v.get('phase')==name and
                bytes.fromhex(v.get('hex','')).endswith(expected+MARKER))
        except AssertionError:raise AssertionError((name,expected,current()))
        evidence[name]=dict(reply=value['hex'])
        time.sleep(.08)
        return capture(hwnd,return_pixels=True)
    def copy_all():
        u.SendMessageW(hwnd,0x112,0x0170,0)
        return clipboard_text(hwnd)
    def key(vk,scan,up=False):
        u.SendMessageW(hwnd,0x101 if up else 0x100,vk,1|scan<<16|(0xc0000000 if up else 0))
    def red_count(pixels):
        return sum(pixels[i:i+3]==b'\xff\0\0' for i in range(0,len(pixels),3))
    def resize(cols,rows):
        assert u.MoveWindow(hwnd,40,40,frame_w+2+cols*cell_w,frame_h+2+rows*cell_h,True)
        wait_snapshot(current,lambda v:(v['columns'],v['rows'])==(cols,rows))
        time.sleep(.15)
    try:
        hwnd=wait_for(lambda:find_window(process.pid));current()
        saved=SavedClipboard(hwnd)
        outer,client=w.RECT(),w.RECT()
        u.GetWindowRect(hwnd,c.byref(outer));u.GetClientRect(hwnd,c.byref(client))
        cell_w,cell_h=(client.right-2)//40,(client.bottom-2)//12
        frame_w,frame_h=outer.right-outer.left-client.right,outer.bottom-outer.top-client.bottom
        image_w,image_h=12*cell_w,2*cell_h
        raster='-'.join('!'+str(image_w)+chr(63+(1<<min(6,image_h-y))-1)
            for y in range(0,image_h,6))
        scene=(CLEAR+'\x1b[48;2;160;0;0m\x1b[1"qKEEP中\x1b[0"q'
            '\x1b[48;2;0;160;0mDROP\x1b[0m\x1b[4;1H\x1b[1"q'+
            ' '*6+'\x1b[0"q\x1b[4;1H\x1bP0;1q"1;1;'+str(image_w)+';'+str(image_h)+
            '#1;2;100;0;0'+raster+'\x1b\\\x1b[H')
        before=phase('protected-scene',scene)
        assert red_count(before)==image_w*image_h,red_count(before)
        erased=phase('selective-display','\x1b[?2J\x1bP$q"q\x1b\\',b'\x1bP1$r0"q\x1b\\')
        assert red_count(erased)==6*cell_w*cell_h,red_count(erased)
        assert copy_all().strip()=='KEEP中',repr(copy_all())
        evidence['selective-display'].update(red_pixels=red_count(erased),copied=copy_all())
        capture(hwnd,'selective-erase-protected.png')
        phase('shift-copy','\x1b[?1002;1006h\x1b[=1u')
        start=(1+cell_h//2)<<16|(1+cell_w//2)
        end=(1+cell_h//2)<<16|(1+5*cell_w+cell_w//2)
        u.SendMessageW(hwnd,0x201,5,start);u.SendMessageW(hwnd,0x200,5,end)
        u.SendMessageW(hwnd,0x202,4,end)
        key(17,29);key(16,42);key(67,46);key(67,46,True);key(16,42,True);key(17,29,True)
        wait_for(lambda:clipboard_text(hwnd)=='KEEP中')
        time.sleep(.1)
        assert bytes.fromhex(current()['hex'])==MARKER,current()
        evidence['shift-copy']['copied']=clipboard_text(hwnd)
        # Clear the selection by a local click before pixel comparisons.
        u.SendMessageW(hwnd,0x201,5,start);u.SendMessageW(hwnd,0x202,4,start)
        resize(60,16)
        after=phase('protected-after-resize','\x1b[?2J')
        assert red_count(after)==6*cell_w*cell_h,red_count(after)
        assert copy_all().strip()=='KEEP中',repr(copy_all())
        evidence['protected-after-resize'].update(red_pixels=red_count(after),dimensions=current())
        phase('alternate-soft-reset','\x1b[?1049h\x1b[H\x1b[1"qALT\x1b[!p\x1b[?25l\x1b[?2J')
        alternate_text=copy_all().rstrip('\r\n')
        # Copy All includes the main buffer above the alternate screen.
        assert alternate_text=='ALT' or alternate_text.endswith('\r\nALT'),repr(alternate_text)
        evidence['alternate-soft-reset']['copied']=alternate_text
        phase('return-main','\x1b[?1049l')
        assert copy_all().strip()=='KEEP中',repr(copy_all())
        style='\x1b[38;2;240;240;240;48;2;0;40;120;4:3m'
        expected=phase('rectangle-reference',CLEAR+style+' \x1b[1"qB\x1b[0"q  EF\x1b[0m')
        actual=phase('selective-rectangle',CLEAR+style+'A\x1b[1"qB\x1b[0"qCDEF'
            '\x1b[0m\x1b[1;1;1;4${')
        assert actual==expected,'selective rectangle changed retained rendition or protected text'
        evidence['selective-rectangle']['pixel_sha256']=hashlib.sha256(actual).hexdigest()
        capture(hwnd,'selective-erase-rectangle.png')
        frozen=phase('frozen-erase','\x1b[?2026h\x1b[?2J')
        assert frozen==actual,'erase escaped synchronized presentation'
        phase('released-erase','\x1b[?2026l')
        wait_for(lambda:capture(hwnd,return_pixels=True)!=actual,timeout=.8)
        assert copy_all().strip()=='B',repr(copy_all())
        phase('ordinary-erases-protected',CLEAR)
        assert not copy_all().strip(),repr(copy_all())
        # Repeated protection changes plus scrollback must retain the bounded
        # memory behavior of ordinary text and respond after erasure.
        payload=''.join(f'\x1b[1"qP{i:04d}\x1b[0"q '+('data '*8)+'\r\n' for i in range(3000))
        phase('history-stress',payload+'\x1b[?2J\x1bP$q"q\x1b\\',b'\x1bP1$r0"q\x1b\\')
        resize(30,16);resize(60,16)
        phase('stress-query','\x1b[1"q\x1b[0m\x1bP$q"q\x1b\\',b'\x1bP1$r1"q\x1b\\')
        assert not errors,errors
        evidence.update(peak_private_ws=max(s['private_ws'] for s in samples),
            peak_total_ws=max(s['total_ws'] for s in samples),
            peak_private_commit=max(s['private_commit'] for s in samples),
            executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest())
        assert evidence['peak_private_ws']<20_000_000,evidence
        assert evidence['peak_total_ws']<50_000_000,evidence
        print('Native selective erase passed:',json.dumps(evidence))
    finally:
        evidence['last_snapshot']=read_snapshot(report)
        (root/'research/selective-erase-observed.json').write_text(json.dumps(evidence,indent=2))
        if saved:saved.restore()
        done.set();worker.join(2);k.CloseHandle(handle)
        write_snapshot(control,{'stop':True});process.wait(timeout=10)
