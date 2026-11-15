"""Replay extended-key resources through owned HWND messages and ConPTY."""
from native_test_utils import (root,c,w,u,hashlib,json,os,subprocess,sys,tempfile,
    Path,time,read_snapshot,write_snapshot,wait_for,find_window)
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile

exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
reference_path=Path(__file__).with_name('extended_keys_reference.json')
reference=json.loads(reference_path.read_text())
assert reference['counts']['native_comparable']==235
marker=b'\x1b[0n'
evidence=dict(completed=False,executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    reference_sha256=hashlib.sha256(reference_path.read_bytes()).hexdigest(),
    physical_input=False,clipboard_access=False,cases={},excluded={})
profile=dict(LinuxFunctionKeys=6,ShiftedArrowKeys=2,WarnOnClose=0,NemoRenderer=0,NemoTabs=0,
             AltF4=0,AltSpace=0,FullScreenOnAltEnter=0,CtrlAltKeys=1,ComposeKey=0,NemoWin32Input=1)
with saved_profile(profile) as profile_args, tempfile.TemporaryDirectory(prefix='nemoterm-extended-keys-') as directory, OwnedJob() as job:
    folder=Path(directory);report,control=folder/'report.json',folder/'control.json'
    process=job.spawn([str(exe),*profile_args,'--cols','80','--rows','24','-e',sys.executable,
        str(root/'tests/mouse_fixture.py'),str(report),str(control),'300'],
        env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1',NEMOTERM_TEST_INPUT_CP='65001'),
        creationflags=subprocess.CREATE_NO_WINDOW)
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
    def event(spec):
        system=bool(spec['mods']&2) or spec['vk'] in (164,165)
        lp=1 | (spec['scan']<<16)
        if not spec['down']:lp|=0xc0000000
        if system:lp|=0x20000000
        u.SendMessageW(hwnd,(0x104 if system else 0x100)+(not spec['down']),spec['vk'],lp)
    try:
        hwnd=wait_for(lambda:find_window(process.pid))
        wait_for(lambda:current().get('columns')==80 and current().get('rows')==24)
        for record in reference['cases']:
            name=record['name']+'/'+str(record['index'])
            if not record['native_comparable']:
                evidence['excluded'][name]=record['native_exclusion'];continue
            if record['reset']:phase('reset-'+name,'\x1bc\x1b[>1;2m\x1b[>2;2m')
            before=bytes.fromhex(record['before_reply_hex'])
            request=phase(name,bytes.fromhex(record['sequence_hex']).decode('ascii'),before)
            for spec in record['events']:event(spec)
            request['input_barrier']=name+'-input';write_snapshot(control,request)
            value=wait_for(lambda:(value:=current()).get('input_barrier')==request['input_barrier'] and value)
            wire=bytes.fromhex(value['hex']);evidence['cases'][name]=wire.hex()
            assert wire==before+marker+bytes.fromhex(record['key_reply_hex'])+marker,(name,wire.hex(),record)
        assert len(evidence['cases'])==235 and len(evidence['excluded'])==74
        write_snapshot(control,dict(stop=True));process.wait(timeout=10)
        assert process.returncode==0
        evidence['cleanup']=job.finish()
        assert not evidence['cleanup']['terminated_remaining'] and evidence['cleanup']['after']['active']==0
        evidence['completed']=True
        print('Native extended keys: 235 exact reference steps; legacy, local bindings and unmapped hardware remain separate')
    finally:
        evidence['last_snapshot']=read_snapshot(report)
        evidence.setdefault('cleanup',job.finish(grace=0))
        (root/'research/extended-keys-observed.json').write_text(json.dumps(evidence,indent=2))
