"""Actual OS cursor selection on fixture-owned terminal views in disposable CI.

No injected observer or clipboard use. This fixture moves the runner's pointer
and sends real Shift/button events, so it refuses a non-CI desktop.
"""
from native_test_utils import *
from owned_job import OwnedJob
import argparse
import uuid
import winreg

if os.environ.get('CI') != 'true':
    raise SystemExit('This input fixture is restricted to disposable CI desktops.')
sys.path.insert(0, str(root/'tools'))
import nemoterm_debug as api

parser = argparse.ArgumentParser(description=__doc__)
mode = parser.add_mutually_exclusive_group(required=True)
mode.add_argument('--masks', type=Path)
mode.add_argument('--colour-reference', type=Path)
mode.add_argument('--history-drag', action='store_true')
parser.add_argument('--font', default='Consolas')
parser.add_argument('--conpty', choices=('system','bundled'), default='bundled')
args = parser.parse_args()
exe = Path(os.environ['NEMOTERM_TEST_EXE']).resolve(strict=True)
out = root/'research/pointer-native-window'
out.mkdir(exist_ok=True)

class CursorInfo(c.Structure):
    _fields_ = [('cbSize', w.DWORD), ('flags', w.DWORD),
                ('cursor', w.HANDLE), ('position', w.POINT)]
class IconInfo(c.Structure):
    _fields_ = [('icon', w.BOOL), ('x', w.DWORD), ('y', w.DWORD),
                ('mask', w.HBITMAP), ('color', w.HBITMAP)]
class Bitmap(c.Structure):
    _fields_ = [('kind', w.LONG), ('width', w.LONG), ('height', w.LONG),
                ('stride', w.LONG), ('planes', w.WORD), ('depth', w.WORD), ('bits', c.c_void_p)]
class MouseInput(c.Structure):
    _fields_ = [('x', w.LONG), ('y', w.LONG), ('data', w.DWORD),
                ('flags', w.DWORD), ('time', w.DWORD), ('extra', c.c_size_t)]
class KeyboardInput(c.Structure):
    _fields_ = [('key', w.WORD), ('scan', w.WORD), ('flags', w.DWORD),
                ('time', w.DWORD), ('extra', c.c_size_t)]
class InputUnion(c.Union):
    _fields_ = [('mouse', MouseInput), ('key', KeyboardInput)]
class Input(c.Structure):
    _anonymous_ = ('data',)
    _fields_ = [('kind', w.DWORD), ('data', InputUnion)]

u.GetCursorInfo.argtypes = [c.POINTER(CursorInfo)]
u.GetIconInfo.argtypes = [w.HANDLE, c.POINTER(IconInfo)]
u.LoadCursorW.argtypes, u.LoadCursorW.restype = [w.HINSTANCE, c.c_void_p], w.HANDLE
u.WindowFromPoint.argtypes, u.WindowFromPoint.restype = [w.POINT], w.HWND
u.GetForegroundWindow.restype = w.HWND
u.ClientToScreen.argtypes = [w.HWND, c.POINTER(w.POINT)]
u.SetForegroundWindow.argtypes = [w.HWND]
u.GetCursorPos.argtypes = [c.POINTER(w.POINT)]
u.SetCursorPos.argtypes = [c.c_int, c.c_int]
u.SendInput.argtypes = [w.UINT, c.POINTER(Input), c.c_int]
u.DrawIconEx.argtypes = [w.HDC, c.c_int, c.c_int, w.HANDLE, c.c_int, c.c_int,
                         w.UINT, w.HBRUSH, w.UINT]
g.GetObjectW.argtypes = [w.HGDIOBJ, c.c_int, c.c_void_p]
g.GetBitmapBits.argtypes, g.GetBitmapBits.restype = [w.HBITMAP, w.LONG, c.c_void_p], w.LONG

names = ('alias cell copy crosshair default e-resize ew-resize grab grabbing help move '
         'n-resize ne-resize nesw-resize no-drop not-allowed ns-resize nw-resize '
         'nwse-resize pointer progress s-resize se-resize sw-resize text vertical-text '
         'w-resize wait zoom-in zoom-out').split()
stock = {'default':32512, 'text':32513, 'wait':32514, 'crosshair':32515,
         'nw-resize':32642, 'se-resize':32642, 'nwse-resize':32642,
         'ne-resize':32643, 'sw-resize':32643, 'nesw-resize':32643,
         'e-resize':32644, 'w-resize':32644, 'ew-resize':32644,
         'n-resize':32645, 's-resize':32645, 'ns-resize':32645,
         'move':32646, 'no-drop':32648, 'not-allowed':32648,
         'pointer':32649, 'progress':32650, 'help':32651}
evidence = dict(exe=str(exe), exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                observer='Win32 GetCursorInfo/GetIconInfo and opt-in terminal API',
                requested_font=args.font, conpty=args.conpty, memory_acceptance=False, injected=False, checks=[])
profile = 'pointer-'+uuid.uuid4().hex
registry = 'Software\\Nemo\\Nemoterm\\Sessions\\'+profile
original = w.POINT(); assert u.GetCursorPos(c.byref(original))
shift_down = left_down = False

def publish():
    (out/'observed.json').write_text(json.dumps(evidence, indent=2))

def native_cursor():
    cursor = CursorInfo(); cursor.cbSize = c.sizeof(cursor)
    ok = u.GetCursorInfo(c.byref(cursor))
    if not ok or not cursor.cursor:
        return dict(handle=cursor.cursor,flags=cursor.flags,available=False,
                    api_success=bool(ok),win32_error=k.GetLastError(),
                    position=[cursor.position.x,cursor.position.y]), b''
    info = IconInfo(); assert u.GetIconInfo(cursor.cursor, c.byref(info))
    try:
        mask = Bitmap(); assert g.GetObjectW(info.mask, c.sizeof(mask), c.byref(mask))
        bits = c.create_string_buffer(mask.stride*mask.height)
        assert g.GetBitmapBits(info.mask, len(bits), bits) == len(bits)
        raw = struct.pack('<IIIII', mask.width, mask.height, mask.stride, info.x, info.y)+bits.raw
        return dict(handle=cursor.cursor, flags=cursor.flags,
                    width=mask.width, mask_height=mask.height,
                    hotspot=[info.x,info.y], mask_sha256=hashlib.sha256(raw).hexdigest()), raw
    finally:
        g.DeleteObject(info.mask)
        if info.color: g.DeleteObject(info.color)

def matches(shape, record, raw):
    if not record['handle']:return False
    if shape in stock:
        return record['handle'] == u.LoadCursorW(None, stock[shape])
    path = args.masks/f"pointer-mask-{shape}-{record['width']}.bin"
    return path.is_file() and raw == path.read_bytes()

def pointer_png(record, path):
    # This draws the actual selected native cursor object; desktop screenshots
    # usually omit the hardware cursor. It is not a terminal framebuffer copy.
    width = height = 144
    header = c.create_string_buffer(struct.pack('<IiiHHIIiiII',40,width,-height,1,32,0,width*height*4,0,0,0,0))
    dc = g.CreateCompatibleDC(None); assert dc
    pixels = c.c_void_p()
    bitmap = g.CreateDIBSection(dc,header,0,c.byref(pixels),None,0); assert bitmap
    old = g.SelectObject(dc,bitmap)
    try:
        background = b'\xee\xee\xee\xff'*(width*height)
        c.memmove(pixels,background,len(background))
        assert u.DrawIconEx(dc,8,8,record['handle'],0,0,0,None,3)
        assert g.GdiFlush()
        return capture_result(width,height,c.string_at(pixels,width*height*4),path,return_pixels=True)
    finally:
        g.SelectObject(dc,old);g.DeleteObject(bitmap);g.DeleteDC(dc)

try:
    with tempfile.TemporaryDirectory(prefix='pointer-window-') as tmp, OwnedJob() as job:
        tmp=Path(tmp);known=set();children=[];serial=0;process=None
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,registry) as key:
            for name,value in dict(WarnOnClose=0,CloseOnExit=1,NemoTabs=1,NemoTabSide=0,
                                   NemoRenderer=0,HideMousePtr=0,LogType=2,LogFileClash=1,LogFlush=1).items():
                winreg.SetValueEx(key,name,0,winreg.REG_DWORD,value)
            winreg.SetValueEx(key,'LogFileName',0,winreg.REG_SZ,str(out/'terminal-wire-&P.log'))
        try:
            process=job.spawn([str(exe),'-load',profile,'--automation','--tabs','--cols','80','--rows','24',
                '--font',args.font,'--shell-command',subprocess.list2cmdline(
                    [sys.executable,str(root/'tests/session_fixture.py'),str(tmp)])],
                env=dict(os.environ,NEMOTERM_CONPTY=args.conpty,NEMOTERM_TEST_EXACT_OUTPUT='1',
                         **({'NEMOTERM_TEST_UTF8_INPUT':'1'} if args.history_drag else {})),
                creationflags=subprocess.CREATE_NO_WINDOW)
            instance=wait_for(lambda:next(iter(api.discover(process.pid)),None),timeout=20)
            endpoint=instance['endpoint'];first=instance['sessions'][0]
            host=first['window']; assert first['renderer']==0

            def child_for(seat):
                def arrived():
                    for path in tmp.glob('*.launch.json'):
                        value=read_snapshot(path)
                        if value and value['pid'] not in known:return value
                value=wait_for(arrived);known.add(value['pid'])
                child=dict(seat=seat,control=tmp/f"{value['pid']}.control.json",
                           report=tmp/f"{value['pid']}.report.json",pid=value['pid'])
                wait_for(lambda:read_snapshot(child['report']));children.append(child)
                return child
            first_child=child_for(first)

            def emit(child, sequence, current):
                global serial
                serial+=1
                phase='pointer-'+str(serial)
                query='\x1b]22;?__current__\x1b\\'
                record=dict(phase=phase,session=child['seat']['id'],
                    input_hex=(sequence+query).encode().hex(),current=current,matched=False)
                evidence.setdefault('wire',[]).append(record);publish()
                write_snapshot(child['control'],dict(phase=phase,sequence=sequence+query,preserve_mouse=True))
                expected=('\x1b]22;'+current+'\x1b\\').encode()
                def replied():
                    value=read_snapshot(child['report'])
                    record['last_child_report']=value
                    return value if value and value.get('phase')==phase and expected in bytes.fromhex(value['hex']) else None
                try:
                    reply=wait_for(replied)
                    record.update(reply_hex=reply['hex'],matched=True)
                finally:
                    record['frontend_sessions']=api.request(endpoint)['sessions']
                    publish()

            def point_in(seat, x=None, y=None):
                point=w.POINT(x if x is not None else seat['client_width']//2,
                              y if y is not None else seat['client_height']//2)
                assert u.ClientToScreen(seat['hwnd'],c.byref(point))
                assert u.SetCursorPos(point.x+1,point.y)
                assert u.SetCursorPos(point.x,point.y)
                # SetCursorPos alone can leave a touch-first runner in
                # CURSOR_SUPPRESSED. Deliver actual mouse-class input to the
                # owned foreground view before inspecting the OS cursor.
                assert u.GetForegroundWindow()==host
                moves=(Input*2)()
                for event,delta in zip(moves,(1,-1)):
                    event.kind=0;event.mouse.x=delta;event.mouse.flags=1
                assert u.SendInput(2,moves,c.sizeof(Input))==2
                wait_for(lambda:u.WindowFromPoint(point)==seat['hwnd'])
                return point

            def expect(name,shape,seat,move=True):
                if move:point_in(seat)
                attempts=[]
                def matching():
                    record,raw=native_cursor()
                    if len(attempts)<16:attempts.append(record)
                    return (record,raw) if matches(shape,record,raw) else None
                try:record,raw=wait_for(matching)
                except BaseException:
                    evidence['pointer_failure']=dict(name=name,expected=shape,samples=attempts,
                        frontend_sessions=api.request(endpoint)['sessions'])
                    publish();raise
                record.update(name=name,shape=shape,session=seat['id'])
                evidence['checks'].append(record)
                (out/(str(len(evidence['checks']))+'.mask')).write_bytes(raw)
                pointer_png(record,str(out/(str(len(evidence['checks']))+'.png')))
                publish();return record

            u.SetForegroundWindow(host);wait_for(lambda:u.GetForegroundWindow()==host)
            emit(first_child,'\x1b[2J\x1b[H','0')
            expect('automatic text pointer','text',first)
            if args.history_drag:
                from selection_capture_gestures import verify_gestures
                verify_gestures(host,first,first_child,Input,out,evidence,publish)
            elif args.colour_reference:
                from pointer_colour_comparison import compare_cursor_colours, check_colour_tabs
                compare_cursor_colours(args.colour_reference, first_child, first, out, evidence,
                                       native_cursor, pointer_png, point_in, emit, publish)
                check_colour_tabs(api, endpoint, host, first, first_child, child_for, out, evidence,
                                  native_cursor, pointer_png, point_in, emit, publish)
            else:
                for shape in names:
                    emit(first_child,'\x1b]22;'+shape+'\x1b\\',shape)
                    expect('canonical '+shape,shape,first)

                emit(first_child,'\x1b]22;grab\x1b\\\x1b]22;>wait\x1b\\','wait')
                expect('pushed wait','wait',first)
                emit(first_child,'\x1b]22;<\x1b\\','grab');expect('pop restores grab','grab',first)
                emit(first_child,'\x1b[?1049h','0');expect('fresh alternate automatic','text',first)
                emit(first_child,'\x1b]22;zoom-in\x1b\\','zoom-in');expect('alternate zoom','zoom-in',first)
                emit(first_child,'\x1b[?1049l','grab');expect('main shape restored','grab',first)
                emit(first_child,'\x1b[!p','0');expect('soft reset automatic','text',first)
                emit(first_child,'\x1b]22;grabbing\x1b\\\x1b[?1003;1006h','grabbing')
                expect('shape independent of mouse reporting','grabbing',first)
                emit(first_child,'\x1b[?1003;1006l\x1b]22;zoom-out\x1b\\','zoom-out')
                expect('shape without mouse reporting','zoom-out',first)

                def send_input(event):
                    assert u.GetForegroundWindow()==host,'owned window lost focus'
                    assert u.SendInput(1,c.byref(event),c.sizeof(event))==1
                def shift(down):
                    global shift_down
                    event=Input();event.kind=1;event.key.key=0x10;event.key.flags=0 if down else 2
                    send_input(event);shift_down=down
                def left(down):
                    global left_down
                    event=Input();event.kind=0;event.mouse.flags=2 if down else 4
                    send_input(event);left_down=down
                shift(True);expect('Shift temporarily selects text','text',first,False)
                shift(False);expect('Shift release restores application shape','zoom-out',first,False)
                left(True);expect('local selection overrides application shape','text',first,False)
                point_in(first,first['client_width']//2+32,first['client_height']//2)
                expect('selection drag stays text','text',first,False)
                left(False);expect('selection release restores application shape','zoom-out',first,False)

                link='\x1b]8;;https://example.invalid/nemoterm\x1b\\'
                fill=('L'*(first['cols']-1)+'\r\n')*(first['rows']-1)
                emit(first_child,'\x1b[2J\x1b[H'+link+fill+'\x1b]8;;\x1b\\','zoom-out')
                expect('allowed link hover overrides application shape','pointer',first)
                shift(True);expect('Shift overrides link hover','text',first,False)
                shift(False);expect('link hover restored after Shift','pointer',first,False)
                emit(first_child,'\x1b[2J\x1b[H','zoom-out')
                expect('leaving cleared link restores application shape','zoom-out',first)

                api.request(endpoint,'key',first['id'],struct.pack('<II',ord('T'),3))
                sessions=wait_for(lambda:(s if len(s:=api.request(endpoint)['sessions'])==2 else None))
                second=next(s for s in sessions if s['id']!=first['id']);second_child=child_for(second)
                assert second['active'] and second['window']==host
                emit(second_child,'\x1b]22;cell\x1b\\','cell');front=expect('new tab has its own shape','cell',second)
                emit(first_child,'\x1b]22;wait\x1b\\','wait')
                samples=[]
                for _ in range(30):
                    record,raw=native_cursor();assert matches('cell',record,raw),record
                    samples.append(record['mask_sha256']);time.sleep(.01)
                evidence['hidden_tab_samples']=samples
                expect('hidden tab cannot replace foreground pointer','cell',second,False)
                api.request(endpoint,'key',second['id'],struct.pack('<II',9,2))
                wait_for(lambda:next(s for s in api.request(endpoint)['sessions'] if s['id']==first['id'])['active'])
                expect('tab activation restores saved pointer','wait',first)

                point_in(dict(hwnd=host,client_width=20,client_height=20),10,10)
                # WindowFromPoint observes hit testing, not completion of the
                # queued mouse/WM_SETCURSOR messages. The host class owns an arrow;
                # wait for that independent state before checking output isolation.
                outside=expect('tab strip has its own arrow','default',first,False)
                emit(first_child,'\x1b]22;copy\x1b\\','copy')
                outside_samples=[]
                for _ in range(30):
                    after,raw=native_cursor()
                    assert matches('default',after,raw),(outside,after)
                    outside_samples.append(after['mask_sha256']);time.sleep(.01)
                evidence['outside_view_unchanged']=dict(before=outside,after=after,
                                                        samples=outside_samples)
                expect('re-entering client applies saved shape','copy',first)

            for child in children:write_snapshot(child['control'],{'stop':True})
            evidence['last_child_reports']=[read_snapshot(child['report']) for child in children]
            evidence['exit_code']=process.wait(timeout=15);assert evidence['exit_code']==0
            evidence['cleanup']=job.finish();assert not evidence['cleanup']['terminated_remaining']
            if args.colour_reference:
                assert not evidence['colour_failures'], evidence['colour_failures']
            evidence['completed']=True
        finally:
            # Balance injected input even after a failing assertion; the job
            # owns only our fixture processes, not the runner desktop.
            for active,kind,flag in ((shift_down,1,2),(left_down,0,4)):
                if active:
                    event=Input();event.kind=kind
                    if kind:event.key.key=0x10;event.key.flags=flag
                    else:event.mouse.flags=flag
                    u.SendInput(1,c.byref(event),c.sizeof(event))
            for child in children:write_snapshot(child['control'],{'stop':True})
            if process and process.poll() is None:
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:pass
            evidence.setdefault('cleanup',job.finish(grace=0))
finally:
    if sys.exc_info()[0]:evidence['error']=repr(sys.exc_info()[1])
    u.SetCursorPos(original.x,original.y)
    try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,registry)
    except FileNotFoundError:pass
    publish()
print('Native pointer window:',len(evidence['checks']),'checks passed')
