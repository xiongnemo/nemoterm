"""Observe bell replies, native stacking/focus and unmodified attention API calls.

The two windows and both child jobs belong to this fixture on a disposable CI
desktop. API observation is not a visual taskbar or audible-speaker acceptance.
"""
import os
assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Requires disposable CI desktop'
import frida
import tarfile
from native_test_utils import (root,c,w,u,hashlib,json,subprocess,sys,tempfile,
    Path,time,read_snapshot,write_snapshot,wait_for,find_window,terminal_host)
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile

u.GetForegroundWindow.restype = w.HWND
u.SetForegroundWindow.argtypes = [w.HWND]
u.GetWindow.argtypes,u.GetWindow.restype = [w.HWND,w.UINT],w.HWND
u.GetTopWindow.argtypes,u.GetTopWindow.restype = [w.HWND],w.HWND
u.SetWindowPos.argtypes = [w.HWND,w.HWND,c.c_int,c.c_int,c.c_int,c.c_int,w.UINT]
u.GetWindowLongPtrW.argtypes,u.GetWindowLongPtrW.restype = [w.HWND,c.c_int],c.c_ssize_t
exe = Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
marker = b'\x1b[0n'
with tarfile.open(root/'research/bell-modes-reference.tar.gz') as archive:
    raw = archive.extractfile('reference/bell-modes-xterm.json').read()
assert hashlib.sha256(raw).hexdigest() == 'c5a87d9f9ee75d637293e3a6767d86102be622271720e8ee4b704e5727c9b6b4'
reference = json.loads(raw)
evidence = dict(completed=False,reference_sha256=hashlib.sha256(raw).hexdigest(),
    executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),cases={},cleanup=[],
    observation='Unmodified API calls and actual foreground/Z-order. Visible taskbar appearance and audible sound not certified.',
    platform_policy='Windows focus clears notifications even after 1042 is reset; foreground activation can itself raise a window.')

try:
    for profile in ('00','10','01','11'):
        settings = dict(Beep=0,BeepInd=int(profile[0]),NemoBellRaise=int(profile[1]),
                        NemoBellOnReset=1,BellOverload=0,WarnOnClose=0,NemoRenderer=0)
        with saved_profile(settings) as args, tempfile.TemporaryDirectory(prefix='nemoterm-bell-') as directory, OwnedJob() as job:
            folder = Path(directory)
            children = []
            for name in ('term','other'):
                report,control = folder/(name+'.json'),folder/(name+'-control.json')
                p = job.spawn([str(exe),*args,'--cols','80','--rows','24','-e',sys.executable,
                    str(root/'tests/mouse_fixture.py'),str(report),str(control),'300'],
                    env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1'),
                    creationflags=subprocess.CREATE_NO_WINDOW)
                hwnd = wait_for(lambda: find_window(p.pid))
                wait_for(lambda: read_snapshot(report).get('columns') == 80)
                children.append((p,hwnd,terminal_host(hwnd),report,control))
            process,hwnd,host,report,control = children[0]
            other = children[1][2]
            session = frida.attach(process.pid)
            script = session.create_script('''
                if (Process.pointerSize !== 8) throw new Error('Expected x64');
                const host=ptr('''+json.dumps(hex(host))+'''), events=[];
                const user=Process.getModuleByName('user32.dll');
                Interceptor.attach(user.getExportByName('FlashWindowEx'),{
                    onEnter(args) {
                        this.event=null;
                        if (args[0].add(8).readPointer().equals(host))
                            this.event={api:'FlashWindowEx',flags:args[0].add(16).readU32(),
                                count:args[0].add(20).readU32(),timeout:args[0].add(24).readU32()};
                    },
                    onLeave(result) { if(this.event) { this.event.prior_active=result.toInt32();events.push(this.event); } }
                });
                Interceptor.attach(user.getExportByName('SetWindowPos'),{
                    onEnter(args) {
                        this.event=null;
                        if(args[0].equals(host) && !(args[6].toUInt32()&4))
                            this.event={api:'SetWindowPos',after:args[1].toString(),flags:args[6].toUInt32()};
                    },
                    onLeave(result) { if(this.event) { this.event.result=result.toInt32();events.push(this.event); } }
                });
                rpc.exports={drain() { return events.splice(0); }};
            ''')
            script.load()
            def state():
                order=[]; window=u.GetTopWindow(None)
                while window:
                    order.append(window)
                    window=u.GetWindow(window,2) # GW_HWNDNEXT, top to bottom
                    assert len(order)<10000
                return dict(foreground=u.GetForegroundWindow(),above_other=order.index(host)<order.index(other),
                            topmost=bool(u.GetWindowLongPtrW(host,-20)&8))
            def focus(window):
                assert u.SetForegroundWindow(window)
                wait_for(lambda: u.GetForegroundWindow() == window)
                time.sleep(.05)
            def phase(name,wire,expected=b''):
                write_snapshot(control,dict(phase=name,preserve_mouse=True,sequence=wire.decode('utf-8')+'\x1b[5n'))
                def received():
                    d=read_snapshot(report)
                    assert process.poll() is None and not d.get('error'),d
                    return d if d.get('phase')==name and bytes.fromhex(d.get('hex','')).endswith(marker) else None
                d=wait_for(received)
                assert bytes.fromhex(d['hex'])==expected+marker,(name,d,expected)
                time.sleep(.04)
                late=wait_for(lambda:read_snapshot(report) or None)
                assert late.get('phase')==name and late.get('hex')==d['hex'],('late reply',name,late)
                return d['hex']
            try:
                initial = b'\x1b[?1042$p\x1b[?1043$p'
                phase(profile+'-startup',initial,bytes.fromhex(reference['cases'][profile+'-initial']['steps'][0]['reply_hex']))
                for name,case in reference['cases'].items():
                    if not name.startswith(profile+'-'): continue
                    focus(host) # clears every previous Windows notification
                    defaults = b'\x1b[?1042;1043l\x1b[?1042;1043s'
                    if profile[0]=='1': defaults += b'\x1b[?1042h'
                    if profile[1]=='1': defaults += b'\x1b[?1043h'
                    phase(name+'-prepare',defaults)
                    focus(other)
                    script.exports_sync.drain()
                    flashing=False
                    evidence['cases'][name]=[]
                    for index,step in enumerate(case['steps']):
                        if step['focus']: focus(host if step['focus']=='term' else other)
                        if step['cover']: assert u.SetWindowPos(other,None,0,0,0,0,0x13)
                        before=state(); focus_events=script.exports_sync.drain()
                        if step['focus']=='term' and flashing:
                            assert any(e['api']=='FlashWindowEx' and e['flags']==0 for e in focus_events),focus_events
                            flashing=False
                        actual=phase(name+'/'+str(index),bytes.fromhex(step['sequence_hex']),bytes.fromhex(step['reply_hex']))
                        after=state(); events=script.exports_sync.drain()
                        assert after['foreground']==before['foreground'],(name,index,'focus stolen',before,after)
                        starts=[e for e in events if e['api']=='FlashWindowEx' and e['flags']!=0]
                        raises=[e for e in events if e['api']=='SetWindowPos']
                        for event in raises:
                            assert event['flags']==0x13 and event['after'] in ('0x0','0xffffffffffffffff','0xfffffffffffffffe') and event['result'],event
                        assert after['topmost']==before['topmost'],(name,index,'topmost changed',before,after)
                        expected_start=step['window_after']['urgency'] and not step['window_before']['urgency']
                        assert bool(starts)==expected_start,(name,index,events,step)
                        if starts:
                            assert all(e['flags']==7 for e in starts),starts
                            flashing=True
                        expected_raise=step['window_after']['above_other'] and not step['window_before']['above_other']
                        if expected_raise: assert raises and after['above_other'],(name,index,events,after)
                        if raises: assert after['above_other'],(name,index,after)
                        if not raises: assert after['above_other']==before['above_other'],(name,index,before,after)
                        evidence['cases'][name].append(dict(sequence_hex=step['sequence_hex'],
                            reply_hex=step['reply_hex'],wire_with_barrier_hex=actual,
                            native_before=before,native_after=after,focus_api=focus_events,api=events,
                            reference_before=step['window_before'],reference_after=step['window_after']))
            finally:
                session.detach()
                for p,_,_,_,mailbox in children: write_snapshot(mailbox,dict(stop=True))
                for p,_,_,_,_ in children:
                    p.wait(timeout=10)
                    assert p.returncode==0
            cleanup=job.finish(); evidence['cleanup'].append(cleanup)
            assert not cleanup['terminated_remaining'] and cleanup['after']['active']==0
    assert len(evidence['cases'])==112
    assert sum(len(v) for v in evidence['cases'].values())==192
    evidence['completed']=True
    print('Native bell modes: 112 cases / 192 exact replies; foreground, stacking and real attention API checked')
finally:
    (root/'research/bell-modes-window-observed.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
