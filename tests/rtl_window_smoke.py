"""Owned native RTL glyph presence, cell order, system fallback and resizing."""
from native_test_utils import *
from owned_job import OwnedJob
from gpu_capture import OwnedGPUCapture
import argparse
import uuid
import winreg

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--font',default='Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light')
parser.add_argument('--gdi-only',action='store_true')
args=parser.parse_args()
exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
u.GetClientRect.argtypes=u.GetWindowRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
u.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),font=args.font,
              completed=False,modes=[],clipboard_tested=False)
reference=None
try:
    for requested in ((0,) if args.gdi_only else (0,1,2)):
        profile='rtl-'+uuid.uuid4().hex
        path='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,path) as reg:
            for name,value in dict(NemoRenderer=requested,WarnOnClose=0,LockSize=2,ScrollbackLines=0).items():
                winreg.SetValueEx(reg,name,0,winreg.REG_DWORD,value)
        try:
            with tempfile.TemporaryDirectory(prefix='nemoterm-rtl-') as tmp,OwnedJob() as job:
                report,control=Path(tmp)/'report',Path(tmp)/'control'
                process=job.spawn([str(exe),'-load',profile,'--font',args.font,'--cols','40','--rows','12',
                    '-e',sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control)],
                    env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1'),
                    creationflags=subprocess.CREATE_NO_WINDOW)
                observer=saved=None;handle=k.OpenProcess(0x410,False,process.pid)
                record=dict(requested=requested,checks=[]);evidence['modes'].append(record)
                try:
                    hwnd=wait_for(lambda:find_window(process.pid));wait_for(lambda:read_snapshot(report))
                    active=int(u.GetPropW(hwnd,'NemotermRenderer') or 0);record['active']=active
                    assert active in (1,2,3)
                    if requested==0:assert active==1
                    if requested==1 and os.environ.get('NEMOTERM_REQUIRE_OPENGL')=='1':assert active==2
                    if requested==2 and os.environ.get('NEMOTERM_REQUIRE_DIRECTX')=='1':assert active==3
                    serial=0
                    def send(sequence):
                        global serial
                        serial+=1
                        write_snapshot(control,dict(phase=serial,sequence=sequence+'\x1b[5n'))
                        wait_snapshot(lambda:read_snapshot(report),lambda v:
                            v.get('phase')==serial and '\x1b[0n'.encode().hex() in v.get('hex',''))
                        # DSR acknowledges parsing; WM_PAINT may still defer
                        # a pending terminal update. This owned-HWND focus
                        # notification runs term_update synchronously, as in
                        # the renderer fixture, without moving desktop focus.
                        # The cursor is hidden throughout these pixel cases.
                        u.SendMessageW(hwnd,0x8,0,0)
                    def frame(text,anchor=True):
                        send('\x1b[?2026l\x1b[0m\x1b[?25l\x1b]10;#ffffff\x07\x1b]11;#000000\x07'
                             '\x1b[2J\x1b[3J\x1b[2;1H'+('L ' if anchor else '')+text)
                        return observer.capture(return_pixels=True)
                    def cell(pixels,col=2,row=1,columns=1,rows=1):
                        rect=w.RECT();assert u.GetClientRect(hwnd,c.byref(rect))
                        cw,ch=(rect.right-2)//40,(rect.bottom-2)//12
                        left,top=(rect.right-cw*40)//2,(rect.bottom-ch*12)//2
                        return b''.join(pixels[((top+row*ch+y)*rect.right+left+col*cw)*3:
                            ((top+row*ch+y)*rect.right+left+(col+columns)*cw)*3] for y in range(rows*ch))
                    send('\x1b[?25l\x1b[2J\x1b[Hאבג ابت\r\nא\u05b0 ب\u064e')
                    record['memory_before_capture']=memory_sample(handle)
                    observer=OwnedGPUCapture(process.pid,hwnd)
                    record['capture_instrumented']=True
                    characters='אבג\ufe8d\ufe91\ufe96'
                    glyphs={ch:cell(frame(ch)) for ch in characters}
                    observer.capture(f'rtl-{requested}-last-reference.png')
                    for ch,pixels in glyphs.items():assert any(pixels),('blank glyph',hex(ord(ch)))
                    assert len(set(glyphs.values()))==len(glyphs),'different letters share a missing-glyph box'
                    record['checks'].append('six distinct nonblank Hebrew and Arabic glyphs')
                    hebrew=frame('אבג')
                    assert [cell(hebrew,col) for col in (2,3,4)]==[glyphs[ch] for ch in 'גבא'],'Hebrew visual cell order'
                    rtl_paragraph=frame('אבג',anchor=False)
                    assert [cell(rtl_paragraph,col) for col in (37,38,39)]==[glyphs[ch] for ch in 'גבא'],'RTL paragraph placement'
                    arabic=frame('ابت')
                    assert [cell(arabic,col) for col in (2,3,4)]==[glyphs[ch] for ch in '\ufe96\ufe91\ufe8d'],'Arabic contextual forms and visual cell order'
                    record['checks'].append('Hebrew order and Arabic shaping preserve exact terminal cells')
                    mixed=frame('L אבג R')
                    assert [cell(mixed,col) for col in (4,5,6)]==[glyphs[ch] for ch in 'גבא']
                    blank=frame('L     R')
                    assert cell(mixed,2)==cell(blank,2) and cell(mixed,8)==cell(blank,8),'fallback overwrote adjacent Latin cells'
                    record['checks'].append('mixed RTL and Latin retain neighboring glyphs')
                    combined=cell(frame('א\u05b0'))
                    assert combined!=glyphs['א'] and any(combined)
                    record['checks'].append('combining mark changes the visible cluster')
                    catalog=frame('אבג ابت\r\nL אבג R\r\nא\u05b0 ب\u064e\r\n\x1b[1mאבג ابت\x1b[0m')
                    observer.capture(f'rtl-{requested}.png')
                    if reference is None:reference=catalog
                    else:
                        assert len(catalog)==len(reference)
                        error=max(abs(a-b) for a,b in zip(catalog,reference))
                        changed=sum(a!=b for a,b in zip(catalog,reference))
                        assert error<=2 and changed<=len(catalog)//1000,(error,changed)
                    send('\x1b[?2026h\x1b[2J\x1b[Hhidden')
                    assert observer.capture(return_pixels=True)==catalog
                    send('\x1b[?2026l')
                    assert observer.capture(return_pixels=True)!=catalog
                    record['checks'].append('compositor parity and synchronized frame preservation')
                    outer,client=w.RECT(),w.RECT()
                    u.GetWindowRect(hwnd,c.byref(outer));u.GetClientRect(hwnd,c.byref(client))
                    assert u.MoveWindow(hwnd,outer.left,outer.top,outer.right-outer.left+(client.right-2)//2,
                        outer.bottom-outer.top+(client.bottom-2)//2,True)
                    resized={ch:cell(frame(ch)) for ch in characters}
                    observer.capture(f'rtl-{requested}-resized.png')
                    record['resized_report']=read_snapshot(report)
                    record['resized_ink']={hex(ord(ch)):sum(bool(b) for b in p) for ch,p in resized.items()}
                    assert all(any(p) for p in resized.values()) and len(set(resized.values()))==6
                    record['checks'].append('font resize retains distinct fallback glyphs')
                    if os.environ.get('CI')=='true':
                        from clipboard_test_utils import SavedClipboard,clipboard_text
                        saved=SavedClipboard(hwnd);frame('אבג')
                        previous=u.GetClipboardSequenceNumber();u.SendMessageW(hwnd,0x111,0x170,0)
                        wait_for(lambda:u.GetClipboardSequenceNumber()!=previous)
                        assert clipboard_text(hwnd).strip()=='L אבג'
                        evidence['clipboard_tested']=True
                        record['checks'].append('real clipboard preserves logical Hebrew order')
                        saved.restore();saved=None
                    observer.close();observer=None
                    u.PostMessageW(hwnd,0x10,0,0);assert process.wait(timeout=10)==0
                    record['cleanup']=job.finish(grace=5);assert not record['cleanup']['terminated_remaining']
                finally:
                    if saved:saved.restore()
                    if observer:observer.close()
                    k.CloseHandle(handle)
                    record.setdefault('cleanup',job.finish(grace=0))
        finally:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,path)
    evidence['completed']=True
finally:
    if sys.exc_info()[0]:
        evidence['error']=repr(sys.exc_info()[1])
        (root/'build'/('rtl-failure-'+uuid.uuid4().hex+'.json')).write_text(json.dumps(evidence,indent=2))
    (root/'research/rtl-window-observed.json').write_text(json.dumps(evidence,indent=2))
print('Native RTL glyph presence, order, shaping and font resize passed:',args.font)
