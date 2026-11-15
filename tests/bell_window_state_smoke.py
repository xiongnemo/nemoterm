"""Bell attention lifetime for owned tab hosts on a disposable CI desktop."""
import os
assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Requires disposable CI desktop'
import frida
from native_test_utils import (root,c,w,u,hashlib,json,subprocess,sys,tempfile,
    Path,time,read_snapshot,write_snapshot,wait_for,find_window,terminal_host)
from owned_job import OwnedJob
from owned_window_focus import focus_owned_window
from protocol_oracle_window import saved_profile
sys.path.insert(0,str(root/'tools'))
import nemoterm_debug as api

u.GetForegroundWindow.restype=w.HWND
u.SetForegroundWindow.argtypes=[w.HWND]
u.GetWindow.argtypes,u.GetWindow.restype=[w.HWND,w.UINT],w.HWND
u.GetTopWindow.argtypes,u.GetTopWindow.restype=[w.HWND],w.HWND
u.GetWindowLongPtrW.argtypes,u.GetWindowLongPtrW.restype=[w.HWND,c.c_int],c.c_ssize_t
u.SetWindowPos.argtypes=[w.HWND,w.HWND,c.c_int,c.c_int,c.c_int,c.c_int,w.UINT]
u.ShowWindow.argtypes=[w.HWND,c.c_int]
u.IsIconic.argtypes=[w.HWND]
exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
evidence=dict(completed=False,executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    checks=[],cleanup=[],focus_actions=[],window_events=[],scope='Actual owned Windows state and unmodified API observation; no speaker or visible taskbar acceptance.')
marker=b'\x1b[0n'

try:
    for renderer in (0,2):
        settings=dict(Beep=0,BeepInd=0,NemoBellRaise=0,NemoBellOnReset=0,
                      BellOverload=0,WarnOnClose=0,CloseOnExit=1,NemoRenderer=renderer)
        with saved_profile(settings) as args,tempfile.TemporaryDirectory(prefix='nemoterm-bell-state-') as directory,OwnedJob() as job:
            folder=Path(directory);tab_folder=folder/'tabs';tab_folder.mkdir()
            environment=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1')
            process=job.spawn([str(exe),*args,'--automation','--tabs','--cols','80','--rows','24',
                '-e',sys.executable,str(root/'tests/session_fixture.py'),str(tab_folder)],
                env=environment,creationflags=subprocess.CREATE_NO_WINDOW)
            other_report,other_control=folder/'other.json',folder/'other-control.json'
            cover=job.spawn([str(exe),*args,'--cols','80','--rows','24','-e',sys.executable,
                str(root/'tests/mouse_fixture.py'),str(other_report),str(other_control),'300'],
                env=environment,creationflags=subprocess.CREATE_NO_WINDOW)
            instance=wait_for(lambda:next(iter(api.discover(process.pid)),None))
            endpoint=instance['endpoint'];first=instance['sessions'][0]
            assert first['renderer']==renderer and first['active'],first
            host=first['window'];other=terminal_host(wait_for(lambda:find_window(cover.pid)))
            serial=0;known=set();children=[]
            def child():
                def launched():
                    for path in tab_folder.glob('*.launch.json'):
                        d=read_snapshot(path)
                        if d and d['pid'] not in known:return d
                d=wait_for(launched);known.add(d['pid']);assert d['parent']==process.pid
                item=dict(pid=d['pid'],report=tab_folder/f"{d['pid']}.report.json",
                          control=tab_folder/f"{d['pid']}.control.json")
                wait_for(lambda:read_snapshot(item['report']).get('columns')==80)
                children.append(item);return item
            first_child=child()
            # Duplicate the fixture command. New-tab intentionally launches the
            # configured shell, which would not create our second VT mailbox.
            u.SendMessageW(first['hwnd'],0x111,0x30,0) # WM_COMMAND / IDM_DUPSESS
            sessions=wait_for(lambda:(s if len(s:=api.request(endpoint)['sessions'])==2 else None))
            second=next(s for s in sessions if s['id']!=first['id'])
            second_child=child()
            assert second['active'] and second['window']==host and second['renderer']==renderer,second
            def phase(target,name,wire):
                global serial
                serial+=1
                write_snapshot(target['control'],dict(phase=serial,preserve_mouse=True,sequence=wire+'\x1b[5n'))
                def received():
                    d=read_snapshot(target['report'])
                    assert process.poll() is None and cover.poll() is None and not d.get('error'),d
                    return d if d.get('phase')==serial and bytes.fromhex(d.get('hex','')).endswith(marker) else None
                d=wait_for(received)
                assert bytes.fromhex(d['hex'])==marker,(name,d)
                time.sleep(.04)
                late=wait_for(lambda:read_snapshot(target['report']) or None)
                assert late.get('phase')==serial and late.get('hex')==d['hex'],(name,late)
                return d['hex']
            def state():
                order=[];window=u.GetTopWindow(None)
                while window:
                    order.append(window);window=u.GetWindow(window,2);assert len(order)<10000
                sessions=api.request(endpoint)['sessions']
                active=[s['id'] for s in sessions if s['active']]
                assert len(active)==1
                return dict(foreground=u.GetForegroundWindow(),above_other=order.index(host)<order.index(other),
                            topmost=bool(u.GetWindowLongPtrW(host,-20)&8),minimized=bool(u.IsIconic(host)),
                            active=active[0],sessions=[s['id'] for s in sessions])
            def focus(window):
                assert window in (host,other)
                evidence['focus_actions'].append(focus_owned_window(window,process.pid if window==host else cover.pid))
            def position(window,after):
                assert u.SetWindowPos(window,after,0,0,0,0,0x13)
            session=frida.attach(process.pid)
            script=session.create_script('''
                const host=ptr('''+json.dumps(hex(host))+'''), events=[];
                if(Process.pointerSize!==8) throw new Error('Expected x64');
                const user=Process.getModuleByName('user32.dll');
                const foreground=new NativeFunction(user.getExportByName('GetForegroundWindow'),'pointer',[]);
                const getFocus=new NativeFunction(user.getExportByName('GetFocus'),'pointer',[]);
                const getProc=new NativeFunction(user.getExportByName('GetWindowLongPtrW'),'pointer',['pointer','int']);
                const windowEvents=[];
                for (const window of [host,ptr('''+json.dumps(hex(first['hwnd']))+''')]) {
                    Interceptor.attach(getProc(window,-4),{
                        onEnter(args) {
                            this.event=null;
                            const msg=args[1].toUInt32();
                            if([6,7,8,134].includes(msg)) {
                                this.event={hwnd:args[0].toString(),message:msg,wparam:args[2].toString(),
                                    before_foreground:foreground().toString(),before_focus:getFocus().toString()};
                                windowEvents.push(this.event);
                            }
                        },
                        onLeave() {if(this.event) {
                            this.event.after_foreground=foreground().toString();
                            this.event.after_focus=getFocus().toString();
                        }}
                    });
                }
                Interceptor.attach(user.getExportByName('FlashWindowEx'),{
                    onEnter(args) { this.event=null;if(args[0].add(8).readPointer().equals(host))
                        this.event={api:'FlashWindowEx',flags:args[0].add(16).readU32()}; },
                    onLeave(result) {if(this.event){this.event.prior_active=result.toInt32();events.push(this.event);}}
                });
                Interceptor.attach(user.getExportByName('SetWindowPos'),{
                    onEnter(args) { this.event=null;if(args[0].equals(host)&&!(args[6].toUInt32()&4))
                        this.event={api:'SetWindowPos',after:args[1].toString(),flags:args[6].toUInt32()}; },
                    onLeave(result) {if(this.event){this.event.result=result.toInt32();events.push(this.event);}}
                });
                rpc.exports={drain(){return events.splice(0);},windowevents(){return windowEvents.splice(0);}};
            ''');script.load()
            def drain():return script.exports_sync.drain()
            def ring(name,target,wire,flash,raise_,above=True):
                drain();before=state();received=phase(target,name,wire);after=state();events=drain()
                record=dict(name=name,renderer=renderer,sequence_hex=wire.encode().hex(),wire_hex=received,
                            before=before,after=after,api=events)
                evidence['checks'].append(record)
                assert after['foreground']==before['foreground'],record
                assert after['active']==before['active']==second['id'],record
                assert after['minimized']==before['minimized'] and after['topmost']==before['topmost'],record
                starts=[e for e in events if e['api']=='FlashWindowEx' and e['flags']!=0]
                raises=[e for e in events if e['api']=='SetWindowPos']
                assert bool(starts)==flash and bool(raises)==raise_,record
                if raise_ and above:assert after['above_other'],record
                for event in raises:assert event['flags']==19 and event['result'],record
                return record
            def clear(name):
                drain();focus(host);events=drain()
                record=dict(name=name,renderer=renderer,after=state(),api=events);evidence['checks'].append(record)
                assert any(e['api']=='FlashWindowEx' and e['flags']==0 for e in events),record
                assert record['after']['active']==second['id'],record
            try:
                focus(other);position(other,None)
                ring('active-unfocused',second_child,'\x1b[?1042;1043h\x07',True,True)
                clear('active-focus-clears')
                ring('background-focused-host',first_child,'\x1b[?1042;1043h\x07',False,True)
                focus(other);position(other,None)
                ring('background-unfocused-host',first_child,'\x07',True,True)
                phase(first_child,'disable-urgent','\x1b[?1042l')
                clear('background-focus-clears-after-disable')
                focus(other);position(other,None)
                ring('background-disabled',first_child,'\x1b[?1042;1043l\x07',False,False)
                position(host,-1);position(other,-1)
                ring('already-topmost',first_child,'\x1b[?1043h\x07',False,True)
                assert state()['topmost']
                position(host,-2);position(other,-2)
                u.ShowWindow(host,6);wait_for(lambda:u.IsIconic(host));focus(other)
                ring('minimized-background',first_child,'\x1b[?1042h\x07',True,True,above=False)
                assert u.IsIconic(host)
                u.ShowWindow(host,9);wait_for(lambda:not u.IsIconic(host));focus(host)
                # Restoring is a fixture action; it must clear the old notice.
                events=drain();assert any(e['api']=='FlashWindowEx' and e['flags']==0 for e in events),events
                evidence['checks'].append(dict(name='restore-clears',renderer=renderer,after=state(),api=events))
                focus(other);position(other,None)
                ring('background-before-close',first_child,'\x07',True,True)
                drain();write_snapshot(first_child['control'],dict(stop=True))
                wait_for(lambda:len(api.request(endpoint)['sessions'])==1)
                events=drain();after=state()
                record=dict(name='notifying-background-close',renderer=renderer,after=after,api=events)
                evidence['checks'].append(record)
                assert after['active']==second['id'] and after['foreground']==other,record
                assert any(e['api']=='FlashWindowEx' and e['flags']==0 for e in events),record
                # Two sessions can own notices for the same host. Closing one
                # must leave the other pending until the host gains focus.
                original_second=second
                u.SendMessageW(second['hwnd'],0x111,0x30,0)
                sessions=wait_for(lambda:(s if len(s:=api.request(endpoint)['sessions'])==2 else None))
                second=next(s for s in sessions if s['id']!=original_second['id'])
                third_child=child();assert second['active']
                focus(host);focus(other);position(other,None)
                ring('two-notices-background-owner',second_child,'\x1b[?1042;1043h\x07',True,True)
                ring('two-notices-active-owner',third_child,'\x1b[?1042;1043h\x07',True,True)
                drain();write_snapshot(second_child['control'],dict(stop=True))
                wait_for(lambda:len(api.request(endpoint)['sessions'])==1)
                events=drain();after=state()
                record=dict(name='one-notice-owner-close-preserves-other',renderer=renderer,after=after,api=events)
                evidence['checks'].append(record)
                assert after['active']==second['id'] and after['foreground']==other,record
                assert not any(e['api']=='FlashWindowEx' and e['flags']==0 for e in events),record
                clear('remaining-notice-clears-on-focus')
                # Closing the selected tab while another application has focus
                # selects its neighbour, but must not acknowledge that notice.
                original_third=second
                u.SendMessageW(second['hwnd'],0x111,0x30,0)
                sessions=wait_for(lambda:(s if len(s:=api.request(endpoint)['sessions'])==2 else None))
                second=next(s for s in sessions if s['id']!=original_third['id'])
                fourth_child=child();assert second['active']
                focus(host);focus(other);position(other,None)
                ring('background-before-active-close',third_child,'\x1b[?1042;1043h\x07',True,True)
                ring('active-before-close',fourth_child,'\x1b[?1042;1043h\x07',True,True)
                phase(third_child,'enable-focus-reporting','\x1b[?1004h')
                drain();write_snapshot(fourth_child['control'],dict(stop=True))
                wait_for(lambda:len(api.request(endpoint)['sessions'])==1)
                second=original_third
                events=drain();after=state()
                record=dict(name='inactive-host-active-tab-close',renderer=renderer,after=after,api=events)
                evidence['checks'].append(record)
                assert after['active']==second['id'] and after['foreground']==other,record
                assert not any(e['api']=='FlashWindowEx' and e['flags']==0 for e in events),record
                focus_data=wait_for(lambda:read_snapshot(third_child['report']) or None)
                record['focus_input_hex']=focus_data.get('hex')
                assert record['focus_input_hex']==marker.hex(),record
                clear('new-active-notice-clears-on-foreground')
                focused=wait_for(lambda:(d if (d:=read_snapshot(third_child['report'])).get('hex')==(marker+b'\x1b[I').hex() else None))
                evidence['checks'][-1]['focus_input_hex']=focused['hex']
                phase(third_child,'disable-focus-reporting','\x1b[?1004l')
            finally:
                evidence['window_events'].append(dict(renderer=renderer,host=host,other=other,events=script.exports_sync.windowevents()))
                session.detach()
                for target in children:write_snapshot(target['control'],dict(stop=True))
                write_snapshot(other_control,dict(stop=True))
                process.wait(timeout=10);cover.wait(timeout=10)
                assert process.returncode==cover.returncode==0
            cleanup=job.finish();evidence['cleanup'].append(cleanup)
            assert not cleanup['terminated_remaining'] and cleanup['after']['active']==0
    evidence['completed']=True
    print('Native bell window states:',len(evidence['checks']),'GDI/DirectX tab-host checks passed')
finally:
    (root/'research/bell-window-state-observed.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
