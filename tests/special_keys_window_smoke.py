"""Replay XTerm special-key bytes with messages to an owned native HWND only."""
from native_test_utils import (root,c,w,u,hashlib,json,os,subprocess,sys,tempfile,
    Path,time,read_snapshot,write_snapshot,wait_for,find_window)
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile

exe = Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
reference_path = Path(__file__).with_name('special_keys_reference.json')
reference = json.loads(reference_path.read_text())
assert len(reference['cases']) == 394
marker = b'\x1b[0n'
evidence = dict(completed=False,executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    reference_sha256=hashlib.sha256(reference_path.read_bytes()).hexdigest(),
    physical_input=False,clipboard_access=False,cases={},core_only={})
profile = dict(LinuxFunctionKeys=6,ShiftedArrowKeys=2,WarnOnClose=0,NemoRenderer=0,NemoTabs=0,
               AltF4=0,AltSpace=0,FullScreenOnAltEnter=0,CtrlAltKeys=1,NemoWin32Input=1)

with saved_profile(profile) as profile_args, tempfile.TemporaryDirectory(prefix='nemoterm-special-keys-') as directory, OwnedJob() as job:
    folder = Path(directory)
    report, control = folder/'report.json', folder/'control.json'
    process = job.spawn([str(exe),*profile_args,'--cols','80','--rows','24','-e',
        sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control),'300'],
        env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1',
                 NEMOTERM_TEST_INPUT_CP='65001'),creationflags=subprocess.CREATE_NO_WINDOW)
    def current():
        d = read_snapshot(report)
        assert process.poll() is None and not d.get('error'), d
        return d
    def phase(name, sequence, expected=b''):
        request = dict(phase=name,sequence=sequence+'\x1b[5n',preserve_mouse=True)
        write_snapshot(control,request)
        d = wait_for(lambda: (d:=current()).get('phase') == name and
                     bytes.fromhex(d.get('hex','')).endswith(marker) and d)
        assert bytes.fromhex(d['hex']) == expected+marker,(name,d,expected.hex())
        return request
    def key(vk, scan, down=True, system=False):
        lp = 1 | ((scan & 511) << 16)
        if not down: lp |= 0xc0000000
        if system: lp |= 0x20000000
        u.SendMessageW(hwnd,(0x104 if system else 0x100)+(not down),vk,lp)
    def chord(record):
        held = [(bit,vk,scan) for bit,vk,scan in ((4,17,29),(1,16,42),(2,18,56)) if record['mods'] & bit]
        for bit,vk,scan in held: key(vk,scan,system=bit==2)
        try:
            key(record['vk'],record['scan'],system=bool(record['mods']&2))
            key(record['vk'],record['scan'],False,system=bool(record['mods']&2))
        finally:
            for bit,vk,scan in reversed(held): key(vk,scan,False,system=bit==2)
    try:
        hwnd = wait_for(lambda: find_window(process.pid))
        wait_for(lambda: current().get('columns') == 80 and current().get('rows') == 24)
        for record in reference['cases']:
            name = record['name']+'/'+str(record['index'])
            # Existing local copy/paste and scrolling bindings retain priority.
            # These exact bytes remain covered by the core reference replay.
            if ((record['key'] == 'Insert' and record['mods'] in (1,4,6)) or
                (record['key'] in ('Prior','Next') and record['mods'] == 1)):
                evidence['core_only'][name] = 'Reserved local copy/paste or scroll binding'
                continue
            if record['reset']:
                # Negotiate the default xterm resource values to override the
                # underlying Win32 transport before synthetic HWND key messages.
                phase('reset-'+name,'\x1bc\x1b[>1;2m\x1b[>2;2m')
            before = bytes.fromhex(record['before_reply_hex'])
            expected = bytes.fromhex(record['reply_hex'])
            request = phase(name,bytes.fromhex(record['sequence_hex']).decode('ascii'),before)
            if record['key']: chord(record)
            request['input_barrier'] = name+'-input'
            write_snapshot(control,request)
            d = wait_for(lambda: (d:=current()).get('input_barrier') == request['input_barrier'] and d)
            wire = bytes.fromhex(d['hex'])
            evidence['cases'][name] = wire.hex()
            assert wire == before+marker+bytes.fromhex(record['key_reply_hex'])+marker,(name,wire.hex(),record)
            assert wire.replace(marker,b'') == expected
        assert len(evidence['cases']) == 378 and len(evidence['core_only']) == 16
        write_snapshot(control,dict(stop=True))
        process.wait(timeout=10)
        assert process.returncode == 0
        evidence['cleanup'] = job.finish()
        assert not evidence['cleanup']['terminated_remaining'] and evidence['cleanup']['after']['active'] == 0
        evidence['completed'] = True
        print('Native special keys: 378 exact reference steps; 16 locally reserved combinations covered in core')
    finally:
        evidence['last_snapshot'] = read_snapshot(report)
        evidence.setdefault('cleanup',job.finish(grace=0))
        (root/'research/special-keys-observed.json').write_text(json.dumps(evidence,indent=2))
