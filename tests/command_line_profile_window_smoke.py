"""Explicit CLI options override loaded profiles in either argument order."""
from native_test_utils import (root,c,w,u,hashlib,json,os,subprocess,sys,tempfile,
    Path,read_snapshot,write_snapshot,wait_for)
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile
sys.path.insert(0,str(root/'tools'))
import nemoterm_debug as api

exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
u.GetClassNameW.argtypes=[w.HWND,w.LPWSTR,c.c_int]
u.ClientToScreen.argtypes=[w.HWND,c.POINTER(w.POINT)]
evidence=dict(completed=False,executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
              checks=[],cleanup=[],physical_input=False,clipboard_access=False)
settings=dict(NemoTabs=0,NemoTabSide=0,NemoRenderer=0,WarnOnClose=0,CloseOnExit=1,
              TermWidth=54,TermHeight=17,Font='Consolas',FontHeight=9,WindowBorder=1,ScrollBar=0)
flags=['--tabs','--tab-side','left','--cols','45','--rows','13','--font','Courier New','--font-size','14']
try:
    with saved_profile(settings) as profile,tempfile.TemporaryDirectory(prefix='nemoterm-cli-profile-') as temporary:
        folder=Path(temporary)
        for name,arguments in [('profile-only',profile),('after-load',[*profile,*flags]),
                               ('before-load',[*flags,*profile]),
                               ('mixed-load',['--tabs','--font-size','14',*profile,'--tab-side','left',
                                              '--cols','45','--rows','13','--font','Courier New']),
                               ('last-value',['--cols','22','--font-size','8',*flags,*profile])]:
            report,control=folder/(name+'-report.json'),folder/(name+'-control.json')
            with OwnedJob() as job:
                command=[str(exe),'--automation',*arguments,'-e',sys.executable,
                         str(root/'tests/mouse_fixture.py'),str(report),str(control)]
                process=job.spawn(command,env=dict(os.environ,NEMOTERM_CONPTY='bundled'),
                                  creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    instance=wait_for(lambda:next(iter(api.discover(process.pid)),None),timeout=20)
                    assert len(instance['sessions'])==1
                    seat=instance['sessions'][0]
                    snapshot=wait_for(lambda:read_snapshot(report))
                    view,host=seat['hwnd'],seat['window']
                    window_class=c.create_unicode_buffer(128)
                    assert u.GetClassNameW(host,window_class,len(window_class))
                    point=w.POINT();outer=w.POINT()
                    assert u.ClientToScreen(view,c.byref(point)) and u.ClientToScreen(host,c.byref(outer))
                    observation=dict(name=name,arguments=arguments,host_class=window_class.value,
                        grid=[snapshot['columns'],snapshot['rows']],view_equals_host=view==host,
                        client=[seat['client_width'],seat['client_height']],offset=[point.x-outer.x,point.y-outer.y])
                    observation['matched']=(observation['grid']==([54,17] if name=='profile-only' else [45,13]) and
                        observation['host_class']==('Nemoterm' if name=='profile-only' else 'NemotermHost') and
                        observation['view_equals_host']==(name=='profile-only'))
                    evidence['checks'].append(observation)
                finally:
                    write_snapshot(control,dict(stop=True))
                    assert process.wait(timeout=15)==0
                    cleanup=job.finish();evidence['cleanup'].append(cleanup)
                    assert not cleanup['terminated_remaining'] and cleanup['after']['active']==0
        reference=evidence['checks'][1]
        for observation in evidence['checks'][2:]:
            observation['matched'] &= (observation['client']==reference['client'] and observation['offset']==reference['offset'])
        assert all(item['matched'] for item in evidence['checks']),evidence['checks']
        assert reference['offset'][0]>=100 and reference['offset'][1]==0,reference
        evidence['completed']=True
finally:
    (root/'research/command-line-profile-observed.json').write_text(json.dumps(evidence,indent=2)+'\n')
print('Command-line profile precedence passed:',len(evidence['checks']),'owned-window cases')
