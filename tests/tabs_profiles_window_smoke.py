"""Saved profiles with different fonts/renderers share one native tab host."""
from native_test_utils import *
from owned_job import OwnedJob
from gpu_capture import OwnedGPUCapture
import re
import uuid
import winreg

exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
font='Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light'
u.GetSystemMenu.argtypes,u.GetSystemMenu.restype=[w.HWND,w.BOOL],w.HMENU
u.GetSubMenu.argtypes,u.GetSubMenu.restype=[w.HMENU,c.c_int],w.HMENU
u.GetMenuItemCount.argtypes=[w.HMENU]
u.GetMenuItemID.argtypes,u.GetMenuItemID.restype=[w.HMENU,c.c_int],w.UINT
u.GetMenuStringW.argtypes=[w.HMENU,w.UINT,w.LPWSTR,c.c_int,w.UINT]
u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
u.GetWindowRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
u.GetGuiResources.argtypes,u.GetGuiResources.restype=[w.HANDLE,w.DWORD],w.DWORD
k.GetProcessHandleCount.argtypes=[w.HANDLE,c.POINTER(w.DWORD)]
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
              completed=False,font=font,checks=[],profiles=[],cycles=[],memory_instrumented=True)
profiles=[]
def menu_command(menu,label):
    for i in range(u.GetMenuItemCount(menu)):
        text=c.create_unicode_buffer(256)
        u.GetMenuStringW(menu,i,text,len(text),0x400)
        if text.value==label:return u.GetMenuItemID(menu,i)
        sub=u.GetSubMenu(menu,i)
        if sub:
            result=menu_command(sub,label)
            if result is not None:return result
    return None
try:
    with tempfile.TemporaryDirectory(prefix='nemoterm-tab-profiles-') as tmp,OwnedJob() as job:
        tmp=Path(tmp);known=set();serial=0;captures=[];session=None
        for renderer in range(3):
            name='tab-profile-'+uuid.uuid4().hex
            path='Software\\Nemo\\Nemoterm\\Sessions\\'+name
            profiles.append(path)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,path) as registry:
                for key,value in dict(WarnOnClose=0,CloseOnExit=1,NemoTabs=1,NemoTabSide=0,
                        NemoRenderer=renderer,FontHeight=10+renderer*2,FontIsBold=0,FontCharSet=1,
                        NemoNextTabBinding=0x64e if renderer==2 else 0x209,
                        TermWidth=83,TermHeight=27).items():
                    winreg.SetValueEx(registry,key,0,winreg.REG_DWORD,value)
                for key,value in dict(Protocol='conpty',Font=font,RemoteCommand=subprocess.list2cmdline(
                        [sys.executable,str(root/'tests/session_fixture.py'),str(tmp)])).items():
                    winreg.SetValueEx(registry,key,0,winreg.REG_SZ,value)
            evidence['profiles'].append(dict(name=name,requested_renderer=renderer,font_size=10+renderer*2))
        process=job.spawn([str(exe),'-load',evidence['profiles'][0]['name']],
            env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
        handle=k.OpenProcess(0x410,False,process.pid)
        try:
            def new_child():
                def launched():
                    for path in tmp.glob('*.launch.json'):
                        value=read_snapshot(path)
                        if value and value['pid'] not in known:return value
                child=wait_for(launched);known.add(child['pid'])
                child['hwnd']=wait_for(lambda:find_window(process.pid))
                child['report']=tmp/f"{child['pid']}.report.json"
                child['control']=tmp/f"{child['pid']}.control.json"
                wait_for(lambda:read_snapshot(child['report']))
                return child
            children=[new_child()];host=terminal_host(children[0]['hwnd'])
            for profile in evidence['profiles'][1:]:
                command=menu_command(u.GetSystemMenu(host,False),profile['name'])
                assert command is not None,profile
                u.SendMessageW(children[-1]['hwnd'],0x111,command,0)
                child=new_child();assert terminal_host(child['hwnd'])==host
                children.append(child)
            evidence['checks'].append('saved-session menu opens three distinct profiles in one host')
            def output(child,sequence):
                global serial
                serial+=1;write_snapshot(child['control'],dict(phase=serial,sequence=sequence+'\x1b[5n'))
                return wait_snapshot(lambda:read_snapshot(child['report']),lambda value:
                    value.get('phase')==serial and bytes.fromhex(value.get('hex','')).endswith(b'\x1b[0n'))
            def observed(child):
                # A concurrent atomic mailbox update can briefly deny reads on
                # Windows. Require a real snapshot before checking isolation.
                return wait_snapshot(lambda:read_snapshot(child['report']),lambda value:'hex' in value)
            for index,child in enumerate(children):
                output(child,scene('PROFILE '+str(index),('90;10;10','10;90;10','10;10;90')[index]))
                captures.append(OwnedGPUCapture(process.pid,child['hwnd']))
            import frida
            session=frida.attach(process.pid)
            script=session.create_script((root/'tests/agent_key_probe.js').read_text());script.load()
            current=children[-1]
            def next_tab():
                global serial,current
                custom=current is children[2]
                serial+=1;script.exports_sync.key(dict(id=serial,key=ord('N') if custom else 9,
                    modifiers=[17,162,18,164] if custom else [17,162]))
                u.PostMessageW(current['hwnd'],0x8322,0,0)
                assert wait_for(lambda:script.exports_sync.result())==dict(id=serial)
                current=children[(children.index(current)+1)%len(children)]
                wait_for(lambda:find_window(process.pid)==current['hwnd'])
            def resources():
                count=w.DWORD();assert k.GetProcessHandleCount(handle,c.byref(count))
                return dict(handles=count.value,gdi=u.GetGuiResources(handle,0),user=u.GetGuiResources(handle,1))
            hashes=[]
            for index in range(3):
                next_tab();profile=evidence['profiles'][index]
                profile['actual_renderer']=int(u.GetPropW(current['hwnd'],'NemotermRenderer') or 0)
                if index==0:assert profile['actual_renderer']==1
                if index==2 and os.environ.get('NEMOTERM_REQUIRE_DIRECTX')=='1':assert profile['actual_renderer']==3
                value=output(current,'\x1b[16t')
                match=re.search(rb'\x1b\[6;(\d+);(\d+)t',bytes.fromhex(value['hex']));assert match
                profile['cell']=[int(v) for v in match.groups()]
                hashes.append(captures[index].capture())
                profile['frame_sha256']=hashes[-1]
                token=f'profile-input-{index};'
                for ch in token:u.SendMessageW(current['hwnd'],0x102,ord(ch),1)
                wait_for(lambda:token.encode().hex() in read_snapshot(current['report']).get('hex',''))
                for other in children:
                    if other is not current:assert token.encode().hex() not in observed(other)['hex']
            assert len({tuple(p['cell']) for p in evidence['profiles']})==3
            evidence['checks'].append('each tab retains its own font geometry and requested renderer')
            evidence['checks'].append('input stays in its session and active-profile custom tab bindings work')
            def font_cell(child):
                value=output(child,'\x1b[16t')
                match=re.fullmatch(rb'\x1b\[6;(\d+);(\d+)t\x1b\[0n',bytes.fromhex(value['hex']))
                assert match,value
                return [int(v) for v in match.groups()]
            zoom_outer=w.RECT();u.GetWindowRect(host,c.byref(zoom_outer))
            u.SendMessageW(current['hwnd'],0x111,0x0940,0)
            zoom_cell=font_cell(current)
            assert zoom_cell[0]>evidence['profiles'][2]['cell'][0],zoom_cell
            for index,child in enumerate(children[:2]):
                assert font_cell(child)==evidence['profiles'][index]['cell']
                # A command addressed to a hidden terminal cannot resize it.
                u.SendMessageW(child['hwnd'],0x111,0x0940,0)
                assert font_cell(child)==evidence['profiles'][index]['cell']
            for index in range(3):
                next_tab()
                expected=zoom_cell if index==2 else evidence['profiles'][index]['cell']
                assert font_cell(current)==expected,(index,expected)
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,profiles[index]) as registry:
                    assert winreg.QueryValueEx(registry,'FontHeight')[0]==10+index*2
                if index<2:wait_for(lambda:captures[index].capture()==hashes[index])
            zoom_after=w.RECT();u.GetWindowRect(host,c.byref(zoom_after))
            assert bytes(zoom_after)==bytes(zoom_outer)
            evidence['font_zoom']=dict(active_tab=2,zoomed_cell=zoom_cell,
                                      siblings_unchanged=True,saved_profiles_unchanged=True)
            u.SendMessageW(current['hwnd'],0x111,0x0960,0)
            assert font_cell(current)==evidence['profiles'][2]['cell']
            output(current,scene('PROFILE 2','10;10;90'))
            wait_for(lambda:captures[2].capture()==hashes[2])
            evidence['checks'].append('font zoom remains in its active tab across switches and preserves saved profiles')
            before=w.RECT();u.GetWindowRect(host,c.byref(before))
            old_grid=observed(children[0])
            hidden=output(children[0],'\x1b[2t\x1b[9;1t\x1b[3;77;88t\x1b[8;9;21t\x1b[18t')
            after=w.RECT();u.GetWindowRect(host,c.byref(after))
            assert bytes(before)==bytes(after)
            assert [hidden['columns'],hidden['rows']]==[old_grid['columns'],old_grid['rows']]
            assert find_window(process.pid)==children[2]['hwnd']
            evidence['checks'].append('background window requests preserve host position, size and active session')
            baseline=resources()
            for cycle in range(12):
                for index in range(3):
                    next_tab()
                    evidence['switch_position']=[cycle,index]
                    wait_for(lambda:captures[index].capture()==hashes[index])
                sample=resources();evidence['cycles'].append(sample)
                assert sample['handles']<=baseline['handles']+8,(baseline,sample)
                assert sample['gdi']<=baseline['gdi']+4,(baseline,sample)
                assert sample['user']<=baseline['user']+2,(baseline,sample)
            evidence['checks'].append('36 mixed-renderer switches preserve exact frames and stable handles')
            output(current,'\x1b[?2026h\x1b[2J\x1b[HMIXED RENDERER THAW')
            for index in range(3):next_tab()
            assert captures[2].capture()==hashes[2]
            output(current,'\x1b[?2026l')
            wait_for(lambda:captures[2].capture()!=hashes[2])
            evidence['checks'].append('frozen pixels survive destroying and recreating the shared renderer')
            for helper in captures:helper.close()
            captures=[];session.detach();session=None
            u.PostMessageW(host,0x10,0,0)
            evidence['frontend_exit']=process.wait(timeout=15)
            assert evidence['frontend_exit']==0,evidence['frontend_exit']
            evidence['owned_job_cleanup']=job.finish(grace=5)
            assert not evidence['owned_job_cleanup']['terminated_remaining']
            evidence['completed']=True
        finally:
            if session:session.detach()
            for helper in captures:helper.close()
            k.CloseHandle(handle)
            evidence.setdefault('owned_job_cleanup',job.finish(grace=0))
finally:
    if sys.exc_info()[0]:evidence['error']=repr(sys.exc_info()[1])
    for path in profiles:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,path)
    (root/'research/tabs-profiles-observed.json').write_text(json.dumps(evidence,indent=2))
print('Mixed tab profiles passed:',len(evidence['checks']),'checks')
