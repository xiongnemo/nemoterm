"""Replay legacy modifier masks through owned UI-thread messages and ConPTY."""
from native_test_utils import (root,c,w,u,hashlib,json,os,subprocess,sys,tempfile,
    Path,time,read_snapshot,write_snapshot,wait_for,find_window)
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile
import frida

exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
reference_path=Path(__file__).with_name('legacy_modifiers_reference.json')
reference=json.loads(reference_path.read_text())
assert reference['count']==2872 and reference['native_count']==2704
marker=b'\x1b[0n'
evidence=dict(completed=False,executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    reference_sha256=hashlib.sha256(reference_path.read_bytes()).hexdigest(),
    physical_input=False,clipboard_access=False,thread_keyboard_state_restored=True,
    cases={},startup_cases={},excluded={},profiles={})
profile=dict(ShiftedArrowKeys=2,WarnOnClose=0,NemoRenderer=0,NemoTabs=0,CtrlShiftIns='none',
    AltF4=0,AltSpace=0,FullScreenOnAltEnter=0,CtrlAltKeys=1,ComposeKey=0,NemoWin32Input=1)
u.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]
try:
    for keyboard in (6,8,7):
        with saved_profile(dict(profile,LinuxFunctionKeys=keyboard,NemoWin32Input=keyboard!=8)) as profile_args, \
                tempfile.TemporaryDirectory(prefix='nemoterm-legacy-keys-') as directory, OwnedJob() as job:
            folder=Path(directory);report,control=folder/'report.json',folder/'control.json'
            process=job.spawn([str(exe),*profile_args,'--cols','80','--rows','24','-e',sys.executable,
                str(root/'tests/mouse_fixture.py'),str(report),str(control),'900'],
                env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1',NEMOTERM_TEST_INPUT_CP='65001'),
                creationflags=subprocess.CREATE_NO_WINDOW)
            session=script=None
            observed=evidence['profiles'][str(keyboard)]=dict(pid=process.pid,completed=False)
            def current():
                value=read_snapshot(report)
                assert process.poll() is None and not value.get('error'),value
                return value
            def phase(name,sequence,expected=b''):
                request=dict(phase=name,sequence=sequence+'\x1b[5n',preserve_mouse=True)
                write_snapshot(control,request)
                value=wait_for(lambda:(value:=current()).get('phase')==name and
                    bytes.fromhex(value.get('hex','')).endswith(marker) and value)
                assert bytes.fromhex(value['hex'])==expected+marker,(name,value,expected.hex())
                return request
            def send_events(name,events):
                if events:
                    script.exports_sync.keys(dict(id=name,events=events))
                    assert u.PostMessageW(hwnd,0x8323,0,0)
                    result=wait_for(lambda:script.exports_sync.result())
                    assert result==dict(id=name,count=len(events),restored=True),(result,errors)
                assert not errors,errors
            try:
                hwnd=wait_for(lambda:find_window(process.pid))
                wait_for(lambda:current().get('columns')==80 and current().get('rows')==24)
                session=frida.attach(process.pid)
                script=session.create_script((root/'tests/legacy_modifiers_key_probe.js').read_text())
                errors=[];script.on('message',lambda message,data:errors.append(message) if message['type']=='error' else None)
                script.load()
                if keyboard==8:
                    startup_names={'legacy-'+key for key in ('Up','Home','Delete','F1','F6',
                        'KP_Enter','KP_Add','KP_Divide','KP_1','Help','Menu',
                        'application-KP_1','application-KP_Add','application-KP_Enter')}
                    for record in reference['cases']:
                        if record['name'] not in startup_names or record['index']>=8:continue
                        name='startup-'+record['name']+'/'+str(record['index'])
                        # Mask zero is also the reset default. Project only its
                        # observed key bytes to verify input before negotiation;
                        # count this equivalence check separately from raw replay.
                        phase(name+'-reset','\x1bc')
                        sequence='\x1b=' if '-application-' in record['name'] else ''
                        request=phase(name,sequence)
                        send_events(name,record['events'])
                        request['input_barrier']=name+'-input';write_snapshot(control,request)
                        value=wait_for(lambda:(value:=current()).get('input_barrier')==request['input_barrier'] and value)
                        wire=bytes.fromhex(value['hex']);evidence['startup_cases'][name]=wire.hex()
                        assert wire==marker+bytes.fromhex(record['key_reply_hex'])+marker,(name,wire.hex(),record)
                    assert len(evidence['startup_cases'])==112
                    print('Legacy startup: 112 mask-zero equivalence checks passed',flush=True)
                for record in reference['cases']:
                    if record['profile']!=keyboard:continue
                    name=record['name']+'/'+str(record['index'])
                    if not record['native_comparable']:
                        evidence['excluded'][name]=record['native_exclusion'];continue
                    if record['reset']:phase('reset-'+name,'\x1bc\x1b[>1;2m\x1b[>2;2m')
                    before=bytes.fromhex(record['before_reply_hex'])
                    request=phase(name,bytes.fromhex(record['sequence_hex']).decode('ascii'),before)
                    send_events(name,record['events'])
                    request['input_barrier']=name+'-input';write_snapshot(control,request)
                    value=wait_for(lambda:(value:=current()).get('input_barrier')==request['input_barrier'] and value)
                    wire=bytes.fromhex(value['hex']);evidence['cases'][name]=wire.hex()
                    assert wire==before+marker+bytes.fromhex(record['key_reply_hex'])+marker,(name,wire.hex(),record)
                    if len(evidence['cases'])%200==0:print('Exact native streams',len(evidence['cases']),flush=True)
                script.unload();script=None;session.detach();session=None
                write_snapshot(control,dict(stop=True));process.wait(timeout=10)
                assert process.returncode==0
                observed['cleanup']=job.finish()
                assert not observed['cleanup']['terminated_remaining'] and observed['cleanup']['after']['active']==0
                observed['completed']=True
                print('Legacy key profile',keyboard,'passed',flush=True)
            finally:
                observed['last_snapshot']=read_snapshot(report)
                if script:script.unload()
                if session:session.detach()
                observed.setdefault('cleanup',job.finish(grace=0))
    assert len(evidence['cases'])==2704 and len(evidence['excluded'])==168
    assert len(evidence['startup_cases'])==112
    evidence['completed']=True
    print('Native legacy modifiers: 2704 exact streams; 168 local bindings covered by core')
finally:
    (root/'research/legacy-modifiers-observed.json').write_text(json.dumps(evidence,indent=2))
