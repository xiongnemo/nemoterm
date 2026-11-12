"""Owned native cells and whole-cluster pixels through the actual ConPTY path."""
from native_test_utils import *
from owned_job import OwnedJob
from gpu_capture import OwnedGPUCapture
import re
import uuid
import winreg
import argparse

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--font-resize',action='store_true')
args=parser.parse_args()
prefix='grapheme-font' if args.font_resize else 'grapheme'

exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
font=os.environ.get('NEMOTERM_TEST_FONT','Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light')
cases=[('accent','e\u0301',1),('CJK','\u4e2d',2),('skin','\U0001f44d\U0001f3fd',2),
       ('profession','\U0001f469\u200d\U0001f4bb',2),
       ('family','\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466',2),
       ('flag','\U0001f1e6\U0001f1fa',2),('keycap','1\ufe0f\u20e3',2),
       ('emoji heart','\u2764\ufe0f',2),('text heart','\u2764\ufe0e',1),
       ('Jamo','\u1100\u1161\u11a8',2),('Indic','\u0915\u094d\u0937',1)]
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),font=font,font_resize=args.font_resize,modes=[],completed=False)
u.GetPropW.argtypes=[w.HWND,w.LPCWSTR];u.GetPropW.restype=w.HANDLE
reference=None
try:
    for requested in (0,1,2):
        profile='cluster-test-'+uuid.uuid4().hex
        keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as reg:
            for name,value in dict(WarnOnClose=0,CloseOnExit=1,NemoRenderer=requested,LockSize=2 if args.font_resize else 0).items():
                winreg.SetValueEx(reg,name,0,winreg.REG_DWORD,value)
        try:
            with tempfile.TemporaryDirectory(prefix='nemoterm-cluster-') as tmp,OwnedJob() as job:
                report,control=Path(tmp)/'report',Path(tmp)/'control'
                process=job.spawn([str(exe),'-load',profile,'--cols','80','--rows','24','--font',font,
                    '-e',sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control)],
                    env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1'),
                    creationflags=subprocess.CREATE_NO_WINDOW)
                gpu=saved=key_session=None
                try:
                    hwnd=wait_for(lambda:find_window(process.pid));wait_for(lambda:read_snapshot(report))
                    active=int(u.GetPropW(hwnd,'NemotermRenderer') or 0);assert active in (1,2,3)
                    if requested==1 and os.environ.get('NEMOTERM_REQUIRE_OPENGL')=='1':assert active==2
                    if requested==2 and os.environ.get('NEMOTERM_REQUIRE_DIRECTX')=='1':assert active==3
                    mode=dict(requested=requested,active=active,checks=[],memory_uninstrumented=[])
                    evidence['modes'].append(mode)
                    def send(name,sequence):
                        write_snapshot(control,dict(phase=name,sequence=sequence+'\x1b[5n',preserve_mouse=True))
                        v=wait_snapshot(lambda:read_snapshot(report),lambda v:
                            v.get('phase')==name and bytes.fromhex(v.get('hex','')).endswith(b'\x1b[0n'))
                        return bytes.fromhex(v['hex'])
                    def cursor(name,sequence,row,col):
                        data=send(name,sequence+'\x1b[6n');match=re.search(rb'\x1b\[(\d+);(\d+)R',data)
                        assert match and tuple(map(int,match.groups()))==(row,col),(name,data,row,col)
                        mode['checks'].append(name)
                    assert b'\x1b[?2027;2$y' in send('mode-default','\x1b[?2027$p')
                    assert b'\x1b[?2027;1$y' in send('mode-on','\x1b[?2027h\x1b[?2027$p')
                    for name,text,cells in cases:
                        cursor(name,'\x1b[2J\x1b[H'+text,1,cells+1)
                        u.RedrawWindow(hwnd,None,None,0x185)
                        h=k.OpenProcess(0x410,False,process.pid)
                        try:mode['memory_uninstrumented'].append(memory_sample(h))
                        finally:k.CloseHandle(h)
                    cursor('late-right-margin','\x1b[2J\x1b[1;80H\u2764\ufe0f',2,3)
                    cursor('REP','\x1b[2J\x1b[H'+cases[3][1]+'\x1b[2b',1,7)
                    cursor('legacy','\x1b[?2027l\x1b[2J\x1b[H'+cases[3][1],1,5)
                    send('gallery','\x1b[?2027h\x1b[?25l\x1b[2J\x1b[H'+
                        ''.join(f'{name:<16}{text}|\r\n' for name,text,cells in cases))
                    u.RedrawWindow(hwnd,None,None,0x185)
                    h=k.OpenProcess(0x410,False,process.pid)
                    try:mode['memory_uninstrumented'].append(memory_sample(h))
                    finally:k.CloseHandle(h)
                    mode['peak_private_ws']=max(v['private_ws'] for v in mode['memory_uninstrumented'])
                    if active in (1,3):assert mode['peak_private_ws']<20_000_000,mode
                    if active in (2,3):gpu=OwnedGPUCapture(process.pid,hwnd)
                    def pixels(name):
                        return gpu.capture(name,True) if gpu else capture(hwnd,name,True,print_flags=1)
                    original=pixels(f'{prefix}-{requested}.png')
                    if reference is None:reference=original
                    else:
                        assert len(original)==len(reference)
                        changed=sum(a!=b for a,b in zip(original,reference))
                        error=max(abs(a-b) for a,b in zip(original,reference))
                        assert error<=2 and changed<=len(original)//1000,(requested,changed,error)
                    send('frozen','\x1b[?2026h\x1b[2J\x1b[Hhidden')
                    assert pixels(None)==original
                    send('release','\x1b[?2026l')
                    assert pixels(None)!=original
                    mode['checks'].append('whole-cluster pixels, compositor parity and synchronized frame')

                    # Resize via the real window procedure, exercising either
                    # grid changes or replacement HFONTs and cached DWrite format.
                    outer,client=w.RECT(),w.RECT()
                    u.GetWindowRect(hwnd,c.byref(outer));u.GetClientRect(hwnd,c.byref(client))
                    cw,ch=(client.right-2)//80,(client.bottom-2)//24
                    assert u.MoveWindow(hwnd,outer.left,outer.top,outer.right-outer.left+10*cw,
                        outer.bottom-outer.top+4*ch,True)
                    columns,rows=(80,24) if args.font_resize else (90,28)
                    wait_for(lambda:(v:=read_snapshot(report)).get('columns')==columns and v.get('rows')==rows)
                    cursor('resized cluster','\x1b[2J\x1b[H'+cases[3][1],1,3)
                    u.RedrawWindow(hwnd,None,None,0x185)
                    resized=pixels(f'{prefix}-{requested}-resize.png')
                    r=w.RECT();u.GetClientRect(hwnd,c.byref(r))
                    new_cw,new_ch=(r.right-2)//columns,(r.bottom-2)//rows
                    if args.font_resize:assert new_ch>ch and new_cw>=cw
                    assert any(resized[(y*r.right+1)*3:(y*r.right+1+2*new_cw)*3] != bytes(2*new_cw*3) for y in range(1,1+new_ch))
                    mode['resized_grid']=[columns,rows];mode['cell_pixels']=[new_cw,new_ch]

                    # The local desktop currently denies clipboard access.
                    # CI owns its clipboard; opt-in local runs can use the same
                    # exact native assertion without weakening that CI check.
                    mode['clipboard_tested']=os.environ.get('CI')=='true' or os.environ.get('NEMOTERM_TEST_CLIPBOARD')=='1'
                    if mode['clipboard_tested']:
                        from clipboard_test_utils import SavedClipboard,clipboard_text
                        import frida
                        saved=SavedClipboard(hwnd)
                        key_session=frida.attach(process.pid)
                        script=key_session.create_script((root/'tests/agent_key_probe.js').read_text())
                        errors=[];script.on('message',lambda m,d:errors.append(m) if m.get('type')=='error' else None)
                        script.load();script.exports_sync.isolate_mouse(hex(hwnd))
                        texts=[cases[3][1],cases[4][1],cases[2][1]]
                        def point(x,y):return (1+y*new_ch+new_ch//2)<<16|(1+x*new_cw+new_cw//2)
                        for frozen in (False,True):
                            phase='copy-frozen' if frozen else 'copy-live'
                            sequence='\x1b[?1003;1006h\x1b[2J\x1b[H'+'\r\n'.join(texts)
                            send(phase,sequence)
                            u.RedrawWindow(hwnd,None,None,0x185)
                            copied_texts=texts
                            if frozen:
                                # Local selection deliberately releases sync
                                # output, paints the new frame, then selects
                                # its visible cells. Exercise different whole
                                # clusters in that newly presented frame.
                                copied_texts=list(reversed(texts))
                                send(phase+'-hidden','\x1b[?2026h\x1b[2J\x1b[H'+'\r\n'.join(copied_texts))
                            u.SendMessageW(hwnd,0x201,13,point(0,0))
                            u.SendMessageW(hwnd,0x200,1,point(1,2))
                            u.SendMessageW(hwnd,0x202,0,point(1,2))
                            before=u.GetClipboardSequenceNumber()
                            script.exports_sync.key(dict(id=1+int(frozen),key=67,scan=46,modifiers=[16,17,160,162]))
                            assert u.PostMessageW(hwnd,0x8322,0,0)
                            assert wait_for(lambda:script.exports_sync.result())==dict(id=1+int(frozen))
                            wait_for(lambda:u.GetClipboardSequenceNumber()!=before)
                            assert clipboard_text(hwnd)=='\r\n'.join(copied_texts),(frozen,clipboard_text(hwnd))
                            assert not errors,errors
                            current_phase=phase+'-hidden' if frozen else phase
                            write_snapshot(control,dict(phase=current_phase,preserve_mouse=True,input_barrier='copy'))
                            delivered=wait_snapshot(lambda:read_snapshot(report),lambda v:
                                v.get('phase')==current_phase and v.get('input_barrier')=='copy')
                            assert bytes.fromhex(delivered['hex'])==b'\x1b[0n'*2,delivered
                            if frozen:
                                assert b'\x1b[?2026;2$y' in send('copy-sync-status','\x1b[?2026$p')
                        mode['checks'].append('Shift-Ctrl rectangles and Ctrl-Shift-C preserve clusters; local selection releases sync output before selecting')
                        saved.restore();saved=None
                        key_session.detach();key_session=None
                    if gpu:gpu.close();gpu=None
                    write_snapshot(control,dict(stop=True));assert process.wait(timeout=10)==0
                    mode['owned_job_cleanup']=job.finish(grace=5)
                    assert not mode['owned_job_cleanup']['terminated_remaining']
                finally:
                    if saved:saved.restore()
                    if key_session:key_session.detach()
                    if gpu:gpu.close()
        finally:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
    evidence['completed']=True
finally:
    if sys.exc_info()[0]:evidence['error']=repr(sys.exc_info()[1])
    (root/f'research/{prefix}-window-observed.json').write_text(json.dumps(evidence,indent=2))
print('Native grapheme columns, REP, legacy mode, pixels and synchronization passed')
