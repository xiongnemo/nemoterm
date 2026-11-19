"""Replay retained UDK bytes using physical keys on a disposable CI desktop."""
from native_test_utils import (root,c,w,u,hashlib,json,os,subprocess,sys,tempfile,
    Path,time,read_snapshot,write_snapshot,wait_for,find_window,terminal_host)
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile
import tarfile

assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Requires disposable CI desktop'
u.SetForegroundWindow.argtypes = [w.HWND]
u.GetAsyncKeyState.argtypes = [c.c_int]
u.GetAsyncKeyState.restype = c.c_short
u.keybd_event.argtypes = [w.BYTE,w.BYTE,w.DWORD,c.c_size_t]
exe = Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
marker = b'\x1b[0n'
with tarfile.open(root/'testdata/upstream/dec-udk-reference.tar.gz') as archive:
    raw = archive.extractfile('9b798e2/reference/dec-udk-xterm.json').read()
assert hashlib.sha256(raw).hexdigest() == 'b6917d91165d635fc7d202be432028faa27104fc62e947ddc4d48c046c2dada3'
reference = json.loads(raw)
evidence = dict(completed=False,executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                reference_sha256=hashlib.sha256(raw).hexdigest(),physical_input=True,
                cases={},core_only={},cleanup=[],profiles={})
selected = {}
for name, case in reference['cases'].items():
    try:
        for step in case['steps']:
            bytes.fromhex(step['sequence_hex']).decode('utf-8')
            bytes.fromhex(step['reply_hex']).decode('utf-8')
    except UnicodeDecodeError:
        evidence['core_only'][name] = 'Raw non-UTF-8 framing/payload: Unicode ConPTY is not a byte PTY'
    else: selected[name] = case
assert set(evidence['core_only']) == {'payload-binary','eight-bit-dcs'}
held = set()

def physical(actions):
    for kind, key, down in actions:
        assert kind == 'key'
        vk = 111+int(key[1:]) if key.startswith('F') else {
            'Shift_L':0x10,'Control_L':0x11,'Alt_L':0x12}[key]
        u.keybd_event(vk,0,0 if down else 2,0)
        if down: held.add(vk)
        else: held.discard(vk)
        wait_for(lambda: bool(u.GetAsyncKeyState(vk)&0x8000) == bool(down))
        time.sleep(.025)

try:
    for profile_name, profile_id in [('vt220',7),('default',6)]:
        settings = dict(LinuxFunctionKeys=profile_id,WarnOnClose=0,NemoRenderer=0,
                        AltF4=0,AltSpace=0,FullScreenOnAltEnter=0)
        evidence['profiles'][profile_name] = settings
        with saved_profile(settings) as profile, tempfile.TemporaryDirectory(prefix='nemoterm-udk-') as directory, OwnedJob() as job:
            folder = Path(directory)
            report, control = folder/'report.json',folder/'control.json'
            process = job.spawn([str(exe),*profile,'--cols','80','--rows','24','-e',
                sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control),'300'],
                env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1'),
                creationflags=subprocess.CREATE_NO_WINDOW)
            def current():
                d = read_snapshot(report)
                assert not d.get('error') and process.poll() is None,d
                return d
            def phase(name,sequence,expected=b''):
                request = dict(phase=name,sequence=sequence+'\x1b[5n',preserve_mouse=True)
                write_snapshot(control,request)
                d = wait_for(lambda: (d:=current()).get('phase') == name and
                    bytes.fromhex(d.get('hex','')).endswith(marker) and d)
                assert bytes.fromhex(d['hex']) == expected+marker,(name,d,expected)
                return request,bytes.fromhex(d['hex'])
            def events(request,prefix,actions,expected):
                physical(actions)
                if expected:
                    wait_for(lambda: bytes.fromhex(current().get('hex','')) == prefix+expected)
                else: time.sleep(.1)
                request['input_barrier'] = request['phase']+'-input'
                write_snapshot(control,request)
                d = wait_for(lambda: (d:=current()).get('input_barrier') == request['input_barrier'] and d)
                wire = bytes.fromhex(d['hex'])
                assert wire == prefix+expected+marker,(request['phase'],d,expected.hex())
                return wire
            try:
                hwnd = wait_for(lambda: find_window(process.pid))
                wait_for(lambda: current().get('columns') == 80 and current().get('rows') == 24)
                assert u.SetForegroundWindow(terminal_host(hwnd))
                for vk in [0x10,0x11,0x12,*range(112,132)]:
                    assert not u.GetAsyncKeyState(vk)&0x8000,(vk,'unexpected held key')
                for name,case in selected.items():
                    if case['profile'] != profile_name: continue
                    phase('reset-'+name,'\x1bc\x1b[65;1"p\x1b[?25l')
                    observed = []
                    evidence['cases'][name] = observed
                    for index,step in enumerate(case['steps']):
                        expected_wire = bytes.fromhex(step['wire_with_barriers_hex'])
                        before,after,tail = expected_wire.split(marker)
                        assert not tail
                        request,prefix = phase(name+'/'+str(index),bytes.fromhex(step['sequence_hex']).decode('utf-8'),before)
                        wire = events(request,prefix,step['actions'],after)
                        reply = wire.replace(marker,b'')
                        assert reply.hex() == step['reply_hex']
                        observed.append(dict(sequence_hex=step['sequence_hex'],actions=step['actions'],
                                             reply_hex=reply.hex(),wire_with_barriers_hex=wire.hex()))
                if profile_name == 'vt220':
                    chord = [('key','Shift_L',1),('key','F6',1),('key','F6',0),('key','Shift_L',0)]
                    request,prefix = phase('kitty-priority','\x1bc\x1bP0;1|17/41\x1b\\\x1b[>1u')
                    locks = (64 if u.GetKeyState(20)&1 else 0)|(128 if u.GetKeyState(144)&1 else 0)
                    wire = events(request,prefix,chord,f'\x1b[17;{locks+2}~'.encode())
                    evidence['kitty_priority_wire'] = wire.hex()
                    request,prefix = phase('udk-after-kitty','\x1b[<u')
                    evidence['udk_after_kitty_wire'] = events(request,prefix,chord,b'A').hex()
                write_snapshot(control,dict(stop=True))
                process.wait(timeout=10)
                assert process.returncode == 0
                cleanup = job.finish()
                evidence['cleanup'].append(cleanup)
                assert not cleanup['terminated_remaining'] and cleanup['after']['active'] == 0
            finally:
                evidence['last_snapshot'] = read_snapshot(report)
                for vk in held: u.keybd_event(vk,0,2,0)
                held.clear()
                if process.poll() is None:
                    write_snapshot(control,dict(stop=True))
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired: evidence['failure_cleanup'] = job.finish()
    assert len(evidence['cases']) == 89
    assert sum(len(steps) for steps in evidence['cases'].values()) == 232
    evidence['completed'] = True
    print('Native UDK: 89 reference cases, 232 exact reply streams, Kitty precedence passed')
finally:
    for vk in held: u.keybd_event(vk,0,2,0)
    (root/'research/udk-window-observed.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
