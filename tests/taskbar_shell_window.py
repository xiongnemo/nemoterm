"""Compare per-session progress to the shell's real taskbar API result, without synthesizing Explorer."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from native_test_utils import root, u, wait_for, write_snapshot, read_snapshot
from protocol_oracle_window import saved_profile
from owned_job import OwnedJob
sys.path.insert(0,str(root/'tools'))
import nemoterm_debug as api


def check(tabs):
    renderer=os.environ['RENDERER']
    out=root/'research'/('taskbar-progress-shell-'+renderer+('-tabs' if tabs else '-standalone')+'.json')
    record=dict(tabs=tabs,renderer=renderer,events=[],explorer_pixels_observed=False,completed=False)
    settings=dict(NemoTabs=int(tabs),NemoRenderer={'gdi':0,'directx':2}[renderer],WarnOnClose=0,CloseOnExit=1)
    try:
        with saved_profile(settings) as profile,tempfile.TemporaryDirectory() as tmp,OwnedJob() as job:
            folder=Path(tmp); seen=set(); pending=[]
            process=job.spawn([os.environ['NEMOTERM_TEST_EXE'],*profile,'--automation', '--cols','70','--rows','20',
                '--font',os.environ['NEMOTERM_TEST_FONT'],'-e',sys.executable,str(root/'tests/session_fixture.py'),tmp,'90'],
                env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1'),creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                instance=wait_for(lambda:next(iter(api.discover(process.pid)),None),timeout=15); endpoint=instance['endpoint']
                def new_child():
                    def find():return next((p for p in folder.glob('*.launch.json') if p not in seen and read_snapshot(p)),None)
                    launch=wait_for(find);seen.add(launch); pid=read_snapshot(launch)['pid']; assert read_snapshot(launch)['parent']==process.pid
                    wait_for(lambda:read_snapshot(folder/f'{pid}.report.json')); return pid
                def seats():return api.request(endpoint)['sessions']
                def stop(pid):write_snapshot(folder/f'{pid}.control.json',dict(stop=True))
                def send(pid,payload):
                    phase=str(len(record['events']));write_snapshot(folder/f'{pid}.control.json',dict(phase=phase,sequence='\x1b]9;'+payload+'\x1b\\\x1b[5n'))
                    wait_for(lambda:(v:=read_snapshot(folder/f'{pid}.report.json')) and v.get('phase')==phase and v['hex'].endswith('1b5b306e'))
                def sample(label,expected,window):
                    def check_state():
                        ss=seats();return ss if {s['id']:(s['progress']['state'],s['progress']['value']) for s in ss}==expected else None
                    ss=wait_for(check_state); assert len({s['window'] for s in ss})==1
                    assert all(s['renderer']==settings['NemoRenderer'] for s in ss)
                    def shell_ok(ss):
                        b=ss[0]['taskbar'];return b['button_ready'] and (not b['attempted'] if window is None else
                            b['attempted'] and b['hresult']==0 and (b['state'],b['value'])==window)
                    until=time.monotonic()+1.5
                    while not shell_ok(ss) and time.monotonic()<until:time.sleep(.04);ss=check_state() or ss
                    row=dict(label=label,expected_button=window,sessions=ss,shell_ok=shell_ok(ss)); record['events'].append(row)
                    if not row['shell_ok']:pending.append(label)
                p=new_child(); s=seats()[0]; a=s['id']; sample('no-shell-allocation-for-idle-window',{a:(0,0)},None)
                send(p,'4;1;65');sample('normal',{a:(1,65)},(1,65))
                if tabs:
                    u.SendMessageW(s['hwnd'],0x111,0x30,0); q=new_child()
                    b=wait_for(lambda:next((r['id'] for r in seats() if r['id']!=a and r['active']),None))
                    send(q,'4;1;25');sample('active-tab-wins-tie',{a:(1,65),b:(1,25)},(1,25))
                    send(p,'4;2;');sample('background-error',{a:(2,65),b:(1,25)},(2,65))
                    send(q,'4;4;');sample('error-over-pause',{a:(2,65),b:(4,25)},(2,65))
                    stop(p);sample('close-background-error',{b:(4,25)},(4,25));p=q;a=b
                send(p,'4;3');sample('unknown-duration',{a:(3,25 if tabs else 65)},(3,25 if tabs else 65))
                send(p,'4;0');sample('clear',{a:(0,0)},(0,0))
                stop(p);assert process.wait(timeout=10)==0
                record['cleanup']=job.finish();assert not record['cleanup']['terminated_remaining']
                record['shell_failures']=pending;record['completed']=not pending
            finally:
                if process.poll() is None:
                    for launch in seen:stop(read_snapshot(launch)['pid'])
    finally:out.write_text(json.dumps(record,indent=2),encoding='utf-8')
    return record['completed']

if __name__=='__main__':
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    outcomes=[check(tabs) for tabs in (False,True)];assert all(outcomes),outcomes
