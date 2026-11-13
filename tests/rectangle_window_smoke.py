"""DEC rectangle editing through the actual Win32/ConPTY/pixel/clipboard path."""
import uuid,winreg
from native_test_utils import (root,c,w,u,k,hashlib,json,os,subprocess,sys,tempfile,Path,
    threading,time,read_snapshot,write_snapshot,memory_sample,wait_for,wait_snapshot,find_window,capture)
from clipboard_test_utils import SavedClipboard,clipboard_text
u.GetClientRect.argtypes=u.GetWindowRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
name='rectangle-'+uuid.uuid4().hex
keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+name
with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:
    winreg.SetValueEx(key,'WarnOnClose',0,winreg.REG_DWORD,0)
exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe'))
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),checks=[])
try:
    with tempfile.TemporaryDirectory(prefix='nemoterm-rectangle-') as directory:
        directory=Path(directory);report,control=directory/'report',directory/'control'
        process=subprocess.Popen([str(exe),'-load',name,'--cols','40','--rows','12','-e',sys.executable,
            str(root/'tests/mouse_fixture.py'),str(report),str(control)],env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
        handle=k.OpenProcess(0x410,False,process.pid);samples=[];stopped=threading.Event()
        def sample():
            while not stopped.is_set():
                try:samples.append(memory_sample(handle))
                except OSError:pass
                stopped.wait(.025)
        worker=threading.Thread(target=sample,daemon=True);worker.start();saved=None
        try:
            hwnd=wait_for(lambda:find_window(process.pid));wait_for(lambda:read_snapshot(report))
            def phase(sequence):
                phase.counter+=1;token=str(phase.counter)
                write_snapshot(control,dict(phase=token,sequence=sequence+'\x1b[?2026$p'))
                phase.snapshot=wait_snapshot(lambda:read_snapshot(report),
                    lambda v:v.get('phase')==token and v.get('columns',0)>0 and v.get('rows',0)>0
                    and b'\x1b[?2026;' in bytes.fromhex(v.get('hex','')))
                time.sleep(.08)
                return capture(hwnd,return_pixels=True)
            phase.counter=0
            def frame(rows):
                return '\x1b[0m\x1b[0*x\x1b[?6l\x1b[r\x1b[?25l\x1b]10;#ffffff\x07\x1b]11;#000000\x07\x1b[2J'+''.join(f'\x1b[{y+1};1H'+s for y,s in enumerate(rows))
            grid=[chr(65+y)*12 for y in range(5)]
            expected=grid.copy()
            for y in range(1,4):expected[y]=expected[y][:2]+'Z'*4+expected[y][6:]
            reference=phase(frame(expected));actual=phase(frame(grid)+'\x1b[90;2;3;4;6$x')
            assert actual==reference,'DECFRA pixels';evidence['checks'].append('fill-pixels')
            for direction in ('down','up','right'):
                if direction=='right':
                    source=['ABCDEFGHIJKL'];expected=['ABABCDEFGHKL'];operation='\x1b[1;1;1;8;1;1;3;1$v'
                else:
                    source=grid;expected=grid.copy()
                    if direction=='down':
                        operation='\x1b[1;2;4;5;1;2;3;1$v'
                        for y in range(1,5):expected[y]=expected[y][:2]+source[y-1][1:5]+expected[y][6:]
                    else:
                        operation='\x1b[2;3;5;6;1;1;2;1$v'
                        for y in range(4):expected[y]=expected[y][:1]+source[y+1][2:6]+expected[y][5:]
                reference=phase(frame(expected));actual=phase(frame(source)+operation)
                assert actual==reference,('DECCRA overlap',direction)
                evidence['checks'].append('copy-overlap-'+direction)
            for exact in (False,True):
                expected=[]
                for y,row in enumerate(grid):
                    text=''
                    for x,ch in enumerate(row):
                        affected=y<3 and ((2<=x<5) if exact else (x>=2 if y==0 else x<5 if y==2 else True))
                        text+=('\x1b[1;4m' if affected else '\x1b[0m')+ch
                    expected.append(text+'\x1b[0m')
                reference=phase(frame(expected));actual=phase(frame(grid)+f'\x1b[{2 if exact else 0}*x\x1b[1;3;3;5;1;4$r')
                assert actual==reference,('DECCARA extent',exact)
                # Reversing the same attributes returns every original pixel.
                assert phase('\x1b[1;3;3;5;1;4$t')==phase(frame(grid))
                evidence['checks'].append('attributes-rectangle' if exact else 'attributes-stream')
            reference=phase(frame(['\x1b[7mA B   \x1b[0m']))
            assert phase(frame(['A B'])+'\x1b[2*x\x1b[1;1;1;6;7$r')==reference
            reference=phase(frame(['\x1b[7mA B\x1b[0m']))
            assert phase(frame(['A B'])+'\x1b[1;1;1;6;7$r')==reference
            evidence['checks'].append('written-space-versus-undrawn')
            label='Á中文Z'
            phase(frame(['\x1b]8;id=rect;https://example.org/rectangle\x1b\\'+label+'\x1b]8;;\x1b\\'])+
                '\x1b[1;1;1;6;1;3;2;1$v\x1b[?1000;1006h\x1b[=1u')
            rect=w.RECT();u.GetClientRect(hwnd,c.byref(rect));cw,ch=(rect.right-2)//40,(rect.bottom-2)//12
            saved=SavedClipboard(hwnd)
            start=(1+2*ch+ch//2)<<16|(1+cw+cw//2);end=(1+2*ch+ch//2)<<16|(1+6*cw+cw//2)
            u.SendMessageW(hwnd,0x201,5,start);u.SendMessageW(hwnd,0x200,5,end);u.SendMessageW(hwnd,0x202,4,end)
            for vk,scan in ((17,29),(16,42),(67,46)):u.SendMessageW(hwnd,0x100,vk,1|(scan<<16))
            for vk,scan in ((67,46),(16,42),(17,29)):u.SendMessageW(hwnd,0x101,vk,0xc0000001|(scan<<16))
            assert wait_for(lambda:clipboard_text(hwnd))==label
            saved.restore();saved=None;evidence['shift_copy']=label
            phase('\x1b[?1000l\x1b[=0u');capture(hwnd,'rectangle-copy.png')
            # Cell-pixel erasure stays local when a filled rectangle intersects Sixel.
            raster='\x1b[H\x1b[?80h\x1bP0;1q'+f'"1;1;{cw*6};{ch}#1;2;100;0;0'+('-'.join(f'!{cw*6}~' for _ in range((ch+5)//6)))+'\x1b\\'
            before=phase(frame([])+raster);after=phase('\x1b[88;1;2;1;3$x')
            width=rect.right
            def cell(p,x,y):return b''.join(p[3*((1+y*ch+j)*width+1+x*cw):3*((1+y*ch+j)*width+1+(x+1)*cw)] for j in range(ch))
            for x in (0,3,4,5):assert cell(after,x,0)==cell(before,x,0)
            reference=phase(frame([' XX']))
            for x in (1,2):assert cell(after,x,0)==cell(reference,x,0)
            evidence['checks'].append('sixel-local-erasure')
            reference=phase(frame(['   X']))
            unicode_fill=phase(frame(['   X'])+'\x1b[20013;1;1;1;3$x')
            assert cell(unicode_fill,3,0)==cell(reference,3,0),'Unicode fill overpainted adjacent X'
            for x in range(3):assert any(cell(unicode_fill,x,0))
            reference=phase(frame(['€€€X']))
            assert phase(frame(['   X'])+'\x1b[8364;1;1;1;3$x')==reference
            evidence['checks'].append('unicode-fill-cell-boundaries')
            capture(hwnd,'rectangle-unicode.png')
            expected=grid.copy()
            for y in (2,3):expected[y]=expected[y][:1]+'ZZZ'+expected[y][4:]
            reference=phase(frame(expected))
            assert phase(frame(grid)+'\x1b[3;5r\x1b[?6h\x1b[90;1;2;2;4$x')==reference
            evidence['checks'].append('origin-relative-rectangle')
            outer=w.RECT();u.GetWindowRect(hwnd,c.byref(outer))
            evidence['resize_dimensions']=[]
            for scale in (1.5,.75,1):
                assert u.MoveWindow(hwnd,20,20,outer.right-outer.left+round((rect.right-2)*(scale-1)),outer.bottom-outer.top+round((rect.bottom-2)*(scale-1)),True)
                expected=grid.copy();expected[1]='BBZZZZBBBBBB'
                reference=phase(frame(expected))
                assert phase(frame(grid)+'\x1b[90;2;3;2;6$x')==reference
                # Reuse the acknowledged phase snapshot. A second file read
                # can briefly fail while the child replaces its JSON mailbox.
                state=phase.snapshot;evidence['resize_dimensions'].append([state['columns'],state['rows']])
            assert evidence['resize_dimensions'][-1]==[40,12]
            evidence['checks'].append('resize-then-edit')
            old=phase(frame(grid));assert phase('\x1b[?2026h\x1b[90;1;1;3;4$x')==old
            changed=phase('\x1b[?2026l');assert changed!=old
            evidence['checks'].append('synchronized-editing')
            # Bounded repeated overlapping copies with original text/colour state.
            phase(frame(grid)+('\x1b[1;1;5;12;1;2;2;1$v\x1b[2;2;6;13;1;1;1;1$v'*1500))
            evidence['overlap_stress_copies']=3000
            capture(hwnd,'rectangle-window.png')
            evidence.update(peak_private_ws=max(v['private_ws'] for v in samples),peak_total_ws=max(v['total_ws'] for v in samples),peak_private_commit=max(v['private_commit'] for v in samples))
            assert evidence['peak_private_ws']<20_000_000,evidence
            (root/'research/rectangle-window-observed.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
            print('Native rectangle pixels, Unicode Shift copy, Sixel, synchronized output and bounded overlap passed:',json.dumps(evidence))
        finally:
            if saved:saved.restore()
            stopped.set();worker.join(2);k.CloseHandle(handle);write_snapshot(control,{'stop':True})
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.terminate();process.wait();raise
finally:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
