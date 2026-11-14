"""Owned ConPTY windows: ISO 2022 text/pixel parity and public API paste input."""
from native_test_utils import *
from owned_job import OwnedJob
from automation_capture import OwnedAutomationCapture,api
from protocol_oracle_window import saved_profile

exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
font=os.environ.get('NEMOTERM_TEST_FONT','Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light')
grid=[80,24] if os.environ.get('CI')=='true' else [160,48]
result=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),font=font,
    requested_grid=grid,completed=False,modes=[])
CSI='\x1b['
reset=CSI+'?42l\x1bc'+CSI+'65;1"p\x1b%G'+CSI+'?25l'+CSI+'2;2H'
barrier=CSI+'>q';marker=b'\x1bP>|Nemoterm(PuTTY 0.85)\x1b\\'
scenes=[('german', '\u00c4\u00d6\u00dc\u00df', CSI+'?42h\x1b(K[\\]~'),
        ('portuguese','\u00c3\u00c7\u00d5',CSI+'?42h\x1b(%6[\\]'),
        ('greek-96','\u0391\u0392\u0393','\x1b%@\x1b-F\x0eABC'),
        ('single-shift','\u00c4AA',CSI+'?42h\x1b*K\x1bN[AA'),
        ('upss-greek','\u0391\u0392\u0393','\x1b%@\x1b(<\x1bP1!uF\x1b\\ABC'),
        ('upss-reassign','\u0391\u0392\u0393ABC','\x1b%@\x1b(<\x1bP1!uF\x1b\\ABC\x1bP1!uA\x1b\\ABC'),
        ('upss-cursor','\u0391\u0392\u0393','\x1b%@\x1b(<\x1bP1!uF\x1b\\\x1b7\x1bP1!uA\x1b\\\x1b8ABC')]
try:
    for requested,renderer in [(0,'GDI'),(1,'OpenGL'),(2,'DirectX')]:
        mode=dict(requested=renderer,completed=False,scenes={});result['modes'].append(mode)
        with saved_profile(dict(NemoRenderer=requested,WarnOnClose=0,NemoAllowChecksum=1)) as profile_args, \
            tempfile.TemporaryDirectory(prefix='nemoterm-iso2022-') as temporary, OwnedJob() as job:
            folder=Path(temporary);report=folder/'report.json';control=folder/'control.json'
            process=job.spawn([str(exe),*profile_args,'--automation','--cols',str(grid[0]),'--rows',str(grid[1]),
                '--font',font,'-e',sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control),'150'],
                env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1',NEMOTERM_TEST_UTF8_INPUT='1'),
                creationflags=subprocess.CREATE_NO_WINDOW)
            observer=None
            try:
                hwnd=wait_for(lambda:find_window(process.pid))
                ready=wait_for(lambda:read_snapshot(report))
                mode['actual_grid']=[ready['columns'],ready['rows']]
                assert mode['actual_grid']==grid,mode
                instance=wait_for(lambda:next(iter(api.discover(process.pid)),None))
                session=next(s for s in instance['sessions'] if s['hwnd']==hwnd)
                mode['actual_renderer']=session['renderer']
                # Hosted runners may lack GPU support; record GDI fallback.
                # Local acceptance requires both hardware paths explicitly.
                active=session['renderer']
                assert active in (0,requested),mode
                required={1:'NEMOTERM_REQUIRE_OPENGL',2:'NEMOTERM_REQUIRE_DIRECTX'}.get(requested)
                if required and os.environ.get(required)=='1':assert active==requested,mode
                mode['fallback']=active!=requested
                observer=OwnedAutomationCapture(process.pid,hwnd)
                def phase(name,sequence):
                    write_snapshot(control,dict(phase=name,preserve_mouse=True,sequence=sequence+barrier))
                    def received():
                        value=read_snapshot(report)
                        assert process.poll() is None,process.returncode
                        return value if value and value.get('phase')==name and \
                            bytes.fromhex(value.get('hex','')).endswith(marker) else None
                    return wait_for(received)
                def pixels(name):
                    # Parser completion precedes presentation. Require three
                    # identical retained frames, without manipulating focus.
                    previous=None;same=0;end=time.monotonic()+5
                    while time.monotonic()<end:
                        frame=observer.capture(return_pixels=True)
                        same=same+1 if frame==previous else 0;previous=frame
                        if same>=2:
                            observer.capture(f'iso2022-{requested}-{name}.png')
                            return frame
                        time.sleep(.05)
                    raise AssertionError('owned renderer did not settle')
                phase('blank-reference',reset)
                blank=pixels('blank')
                mode['blank_sha256']=hashlib.sha256(blank).hexdigest()
                for name,unicode_text,sequence in scenes:
                    phase(name+'-unicode',reset+unicode_text)
                    expected=pixels(name+'-unicode')
                    assert expected!=blank,(name,'Unicode baseline is blank')
                    phase(name+'-designated',reset+sequence)
                    actual=pixels(name+'-designated')
                    text=api.request(instance['endpoint'],'text',session['id'])
                    mode['scenes'][name]=dict(expected_sha256=hashlib.sha256(expected).hexdigest(),
                        actual_sha256=hashlib.sha256(actual).hexdigest(),logical_text=text)
                    assert unicode_text in text,(name,text)
                    assert actual==expected,(name,'renderer pixels differ')
                phase('paste-setup',reset+CSI+'?42h\x1b(K')
                before=bytes.fromhex(read_snapshot(report)['hex'])
                text='\u00c4\u00d6\u00dc\u00df'
                api.request(instance['endpoint'],'paste',session['id'],text.encode())
                expected=before+b'[\\]~'
                wait_for(lambda:read_snapshot(report).get('hex')==expected.hex())
                mode['paste_hex']=expected[len(before):].hex()
                # Typing is distinct from NRC selection conversion.
                api.request(instance['endpoint'],'input',session['id'],text.encode())
                expected+=text.encode()
                wait_for(lambda:read_snapshot(report).get('hex')==expected.hex())
                mode['typing_hex']=text.encode().hex()
                upss=phase('upss-paste-setup',reset+CSI+'?42h\x1b(<\x1bP1!uF\x1b\\'+CSI+'&u')
                before=bytes.fromhex(upss['hex'])
                assert before==b'\x1bP1!uF\x1b\\'+marker,before
                api.request(instance['endpoint'],'paste',session['id'],'\u0391\u0392\u0393'.encode())
                wait_for(lambda:read_snapshot(report).get('hex')==(before+b'ABC').hex())
                mode['upss_paste_hex']=b'ABC'.hex()
                write_snapshot(control,dict(stop=True));process.wait(timeout=10)
                assert process.returncode==0,process.returncode
                mode['cleanup']=job.finish();assert not mode['cleanup']['terminated_remaining']
                mode['completed']=True
                print(renderer,'(actual '+['GDI','OpenGL','DirectX'][active]+')',
                    len(scenes),'pixel/text scenes, paste and typing passed',flush=True)
            finally:
                mode['last_snapshot']=read_snapshot(report)
                if observer:observer.close()
                mode.setdefault('cleanup',job.finish(grace=0))
    result['completed']=True
finally:
    (root/'research/iso2022-observed.json').write_text(json.dumps(result,indent=2)+'\n')
