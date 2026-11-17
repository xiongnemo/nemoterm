"""Owned-process checks used by the remote modal-dialog UI fixture."""
from native_test_utils import *
sys.path.insert(0,str(root/'tools'))
import nemoterm_debug as api

pid=int(sys.argv[1]); operation=sys.argv[2]
instance=wait_for(lambda:next(iter(api.discover(pid)),None),timeout=15)
endpoint=instance['endpoint']
u.IsWindowEnabled.argtypes=[w.HWND]
u.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]
u.SetForegroundWindow.argtypes=[w.HWND]
u.GetForegroundWindow.restype=w.HWND
u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
u.GetClassNameW.argtypes=[w.HWND,w.LPWSTR,c.c_int]

def owned_dialog_active():
    foreground=u.GetForegroundWindow();owner=w.DWORD();name=c.create_unicode_buffer(64)
    u.GetWindowThreadProcessId(foreground,c.byref(owner))
    u.GetClassNameW(foreground,name,len(name))
    return owner.value==pid and name.value in ('#32770','PuTTYConfigBox') and u.IsWindowEnabled(foreground)

if operation=='prepare':
    seat=instance['sessions'][0]
    if seat['hwnd']!=seat['window']:
        api.request(endpoint,'key',seat['id'],struct.pack('<II',ord('T'),3))
        pair=wait_for(lambda:(v if len((v:=api.request(endpoint))['sessions'])==2 else None))
        added=next(s for s in pair['sessions'] if s['id']!=seat['id'])
        api.request(endpoint,'key',added['id'],struct.pack('<II',9,2))
    instance=api.request(endpoint);instance['endpoint']=endpoint
elif operation=='blocked':
    report=Path(sys.argv[3])
    before=wait_snapshot(lambda:read_snapshot(report),lambda v:'hex' in v)
    count=len(instance['sessions'])
    for seat in instance['sessions']:
        assert not u.IsWindowEnabled(seat['window']),seat
        u.SetForegroundWindow(seat['window'])
        # Cross-thread activation and the dialog redirect finish asynchronously.
        wait_for(owned_dialog_active)
        for op,payload in [('input','BLOCKED'),('paste','BLOCKED'),
                           ('key',struct.pack('<II',ord('T'),3))]:
            try: api.request(endpoint,op,seat['id'],payload)
            except api.DebugError as error: assert error.status==4,error
            else: raise AssertionError('Dialog allowed '+op)
        u.SendMessageW(seat['hwnd'],0x102,ord('Q'),1)
        u.SendMessageW(seat['window'],0x111,0x20,0)
    time.sleep(.15)
    assert len(api.request(endpoint)['sessions'])==count
    after=wait_snapshot(lambda:read_snapshot(report),lambda v:'hex' in v)
    with (root/'research'/f'dialog-blocked-{pid}.jsonl').open('a',encoding='utf-8') as output:
        output.write(json.dumps(dict(before=before,after=after))+'\n')
    assert after['hex']==before['hex'],('modal input changed',before,after)
elif operation=='ready':
    assert all(u.IsWindowEnabled(s['window']) for s in instance['sessions'])
    seat=next(s for s in instance['sessions'] if s['active'])
    api.request(endpoint,'input',seat['id'],'RESUMED')
    wait_for(lambda:'RESUMED'.encode().hex() in read_snapshot(Path(sys.argv[3])).get('hex',''))
elif operation=='zoom':
    report,control=Path(sys.argv[3]),Path(sys.argv[4])
    seat=next(s for s in instance['sessions'] if s['active'])
    write_snapshot(control,dict(phase='zoom-defaults',sequence='\x1b[>3u\x1b[5n'))
    wait_for(lambda:read_snapshot(report).get('hex')=='1b5b306e')
    rows=seat['rows']
    for plus,mods,minus in [(0xbb,2,0xbd),(0xbb,3,0xbd),(0x6b,2,0x6d)]:
        api.request(endpoint,'key',seat['id'],struct.pack('<II',plus,mods))
        wait_for(lambda:next(s for s in api.request(endpoint)['sessions'] if s['id']==seat['id'])['rows']<rows)
        api.request(endpoint,'key',seat['id'],struct.pack('<II',minus,2))
        wait_for(lambda:next(s for s in api.request(endpoint)['sessions'] if s['id']==seat['id'])['rows']==rows)
    time.sleep(.15)
    final=wait_snapshot(lambda:read_snapshot(report),lambda v:'hex' in v)
    assert final['hex']=='1b5b306e',('zoom keys leaked through CSI-u',final)
elif operation=='finish':
    original=int(sys.argv[3])
    for seat in instance['sessions']:
        if seat['hwnd']!=original: u.PostMessageW(seat['hwnd'],0x10,0,0)
    wait_for(lambda:len(api.request(endpoint)['sessions'])==1)
elif operation!='state':
    raise ValueError(operation)
print(json.dumps(instance))
