"""Real ConPTY/Win32 margin editing, Sixel column scrolling and font changes."""
import uuid,winreg,re
from native_test_utils import (root,c,w,u,k,hashlib,json,os,subprocess,sys,tempfile,Path,
    threading,time,read_snapshot,write_snapshot,memory_sample,wait_for,wait_snapshot,find_window,capture)
from clipboard_test_utils import SavedClipboard,clipboard_text
u.GetClientRect.argtypes=u.GetWindowRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe'))
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),runs=[])

def run(font_resize):
    name='margins-'+uuid.uuid4().hex
    keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+name
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:
        winreg.SetValueEx(key,'WarnOnClose',0,winreg.REG_DWORD,0)
        winreg.SetValueEx(key,'LockSize',0,winreg.REG_DWORD,2 if font_resize else 0)
    record=dict(font_resize=font_resize,checks=[],observations=[])
    try:
        with tempfile.TemporaryDirectory(prefix='nemoterm-margins-') as temporary:
            directory=Path(temporary);report,control=directory/'report',directory/'control'
            process=subprocess.Popen([str(exe),'-load',name,'--cols','40','--rows','12',
                '--font','SarasaTermSC Nerd Font Light','-e',sys.executable,
                str(root/'tests/mouse_fixture.py'),str(report),str(control)],
                env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
            handle=k.OpenProcess(0x410,False,process.pid);samples=[];stop=threading.Event()
            def sample():
                while not stop.is_set():
                    try:samples.append(memory_sample(handle))
                    except OSError:pass
                    stop.wait(.025)
            worker=threading.Thread(target=sample,daemon=True);worker.start();saved=None
            try:
                hwnd=wait_for(lambda:find_window(process.pid));wait_for(lambda:read_snapshot(report))
                def phase(sequence):
                    phase.counter+=1;token=str(phase.counter)
                    write_snapshot(control,dict(phase=token,sequence=sequence+'\x1b[?69$p'))
                    value=wait_snapshot(lambda:read_snapshot(report),lambda v:
                        v.get('phase')==token and b'\x1b[?69;' in bytes.fromhex(v.get('hex','')))
                    time.sleep(.08)
                    return value
                phase.counter=0
                def frame(rows):
                    return '\x1b[?6l\x1b[?69l\x1b[r\x1b[0m\x1b[?25l\x1b]10;#ffffff\x07\x1b]11;#000000\x07\x1b[2J'+''.join(f'\x1b[{y+1};1H'+s for y,s in enumerate(rows))
                margin='\x1b[?69h\x1b[3;8s\x1b[3;6r'
                if not font_resize:
                    grid=[chr(65+y)*12 for y in range(7)]
                    for op,delta,start in (('\x1b[S',1,2),('\x1b[T',-1,2),('\x1b[4;4H\x1b[2L',-2,3),('\x1b[4;4H\x1b[2M',2,3)):
                        expected=grid.copy()
                        for y in range(start,6):
                            middle=grid[y+delta][2:8] if start<=y+delta<6 else ' '*6
                            expected[y]=expected[y][:2]+middle+expected[y][8:]
                        phase(frame(expected));reference=capture(hwnd,return_pixels=True)
                        phase(frame(grid)+margin+op)
                        wait_for(lambda:capture(hwnd,return_pixels=True)==reference)
                    record['checks'].append('SU-SD-IL-DL-pixels')
                    label='Á中文Z'
                    phase(frame(['']*4+[label])+'\x1b[?69h\x1b[1;12s\x1b[3;6r\x1b[S\x1b[?1003;1006h\x1b[=1u')
                    rect=w.RECT();u.GetClientRect(hwnd,c.byref(rect));cw,ch=(rect.right-2)//40,(rect.bottom-2)//12
                    saved=SavedClipboard(hwnd)
                    start=(1+3*ch+ch//2)<<16|(1+cw//2);end=(1+3*ch+ch//2)<<16|(1+5*cw+cw//2)
                    u.SendMessageW(hwnd,0x201,5,start);u.SendMessageW(hwnd,0x200,5,end);u.SendMessageW(hwnd,0x202,4,end)
                    for vk,scan in ((17,29),(16,42),(67,46)):u.SendMessageW(hwnd,0x100,vk,1|(scan<<16))
                    for vk,scan in ((67,46),(16,42),(17,29)):u.SendMessageW(hwnd,0x101,vk,0xc0000001|(scan<<16))
                    assert wait_for(lambda:clipboard_text(hwnd))==label
                    record['shift_copy']=label;capture(hwnd,'margins-copy.png');saved.restore();saved=None
                    phase('\x1b[=0u\x1b[?1003l')
                # Earlier text scenarios deliberately entered history via ED.
                # This pixel model starts with empty history so enlargement
                # cannot legitimately expose those unrelated previous rows.
                phase(frame([])+'\x1b[3J\x1b]12;#00ff00\x07\x1b[2 q\x1b[?25h\x1b[H')
                def raster():
                    rect=w.RECT();u.GetClientRect(hwnd,c.byref(rect));pixels=capture(hwnd,return_pixels=True)
                    green=[];red=set()
                    for i in range(0,len(pixels),3):
                        colour=pixels[i:i+3]
                        if colour==b'\0\xff\0':green.append((i//3%rect.right,i//3//rect.right))
                        elif colour==b'\xff\0\0':red.add((i//3%rect.right,i//3//rect.right))
                    if not green:return None
                    xs,ys=zip(*green)
                    return (min(xs),min(ys),max(xs)-min(xs)+1,max(ys)-min(ys)+1),red
                base=wait_for(raster)[0];width,height=base[2]*12,base[3]*6
                anchors={(x,y):1 for y in range(height) for x in range(width)}
                bands=''.join(f'!{width}{chr(63+(1<<min(6,height-y))-1)}-' for y in range(0,height,6))
                solid=f'\x1bP0;1q"1;1;{width};{height}#1;2;100;0;0'+bands+'\x1b\\'
                phase('\x1b[?80l\x1b[2;3H'+solid+'\x1b[H')
                def check(label):
                    latest=None
                    def matches():
                        nonlocal latest
                        latest=raster()
                        if not latest:return False
                        (ox,oy,cw,ch),actual=latest
                        state=read_snapshot(report)
                        expected={(ox+2*cw+x,oy+anchor*ch+y) for (x,y),anchor in anchors.items()
                            if 0<=anchor*ch+y<state.get('rows',12)*ch and 2*cw+x<state.get('columns',40)*cw}
                        return actual==expected
                    try:wait_for(matches)
                    except AssertionError:
                        capture(hwnd,'margins-failed.png');raise AssertionError((label,latest[0] if latest else None,len(anchors)))
                    record['observations'].append(dict(phase=label,geometry=latest[0],pixels=len(latest[1])))
                    return latest[0]
                geom=check('initial')
                def erase(col,row):
                    _,_,cw,ch=geom
                    for (x,y),anchor in list(anchors.items()):
                        if col*cw<=2*cw+x<(col+1)*cw and row*ch<=anchor*ch+y<(row+1)*ch:
                            del anchors[x,y]
                    phase(f'\x1b[{row+1};{col+1}H\x1b[X\x1b[H');check('erase-hole')
                def scroll(left,right,top,bottom,lines):
                    _,_,cw,ch=geom
                    for (x,y),anchor in list(anchors.items()):
                        at=anchor*ch+y
                        if left*cw<=2*cw+x<right*cw and top*ch<=at<(bottom+1)*ch:
                            if top*ch<=at-lines*ch<(bottom+1)*ch:anchors[x,y]=anchor-lines
                            else:del anchors[x,y]
                    phase(f'\x1b[?69h\x1b[{left+1};{right}s\x1b[{top+1};{bottom+1}r\x1b[{abs(lines)}'+('S' if lines>0 else 'T')+'\x1b[H')
                    return check('partial-up' if lines>0 else 'partial-down')
                erase(6,2);geom=scroll(4,10,2,5,1)
                capture(hwnd,'margins-sixel-font.png' if font_resize else 'margins-sixel.png')
                client,outer=w.RECT(),w.RECT();u.GetClientRect(hwnd,c.byref(client));u.GetWindowRect(hwnd,c.byref(outer))
                for index,(sx,sy) in enumerate(((1.5,1.5),(.75,.75),(1,1))):
                    assert u.MoveWindow(hwnd,20,20,outer.right-outer.left+round((client.right-2)*(sx-1)),outer.bottom-outer.top+round((client.bottom-2)*(sy-1)),True)
                    state=phase('\x1b[?6l\x1b[H\x1bP$qs\x1b\\\x1bP$qr\x1b\\')
                    if font_resize:
                        assert (state['columns'],state['rows'])==(40,12),state
                    else:
                        reply=bytes.fromhex(state['hex'])
                        assert f"\x1bP1$r1;{state['columns']}s\x1b\\".encode() in reply,state
                        assert f"\x1bP1$r1;{state['rows']}r\x1b\\".encode() in reply,state
                        assert b'\x1b[?69;1$y' in reply,state
                    geom=check('resize-'+str(index))
                    geom=scroll(3,8,1,5,-1 if index%2==0 else 1)
                    erase(5,3)
                record['checks'].append('pixel-model-font-resize' if font_resize else 'pixel-model-grid-resize')
                phase('\x1b[?6l\x1b[?69l\x1b[r\x1b[2J'+300*('\x1b[2;3H'+solid+'\x1b[?69h\x1b[5;10s\x1b[3;6r\x1b[S\x1b[T')+'\x1b[H')
                record['checks'].append('300-image-split-scrolls')
                record.update(peak_private_ws=max(s['private_ws'] for s in samples),peak_total_ws=max(s['total_ws'] for s in samples),peak_private_commit=max(s['private_commit'] for s in samples))
                assert record['peak_private_ws']<20_000_000,record
                evidence['runs'].append(record)
            finally:
                if saved:saved.restore()
                stop.set();worker.join(2);k.CloseHandle(handle);write_snapshot(control,dict(stop=True))
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.terminate();process.wait();raise
    finally:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)

run(False);run(True)
for key in ('peak_private_ws','peak_total_ws','peak_private_commit'):evidence[key]=max(r[key] for r in evidence['runs'])
(root/'research/margins-window-observed.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
print('Native margin editing, Sixel pixel model, font/grid resize and bounded storage passed:',json.dumps(evidence))
