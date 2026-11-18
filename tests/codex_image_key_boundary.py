"""Trace only the diagnostic console's keyboard records after replaying Codex output."""
import hashlib,json,os,struct,subprocess,sys,time,traceback,uuid,winreg
from pathlib import Path
from agent_clipboard_fixture import put_bitmap
from clipboard_test_utils import SavedClipboard
from fixture_io import read_snapshot,write_snapshot
from hosted_gesture_input import DesktopInput
from native_test_utils import wait_for
from owned_job import OwnedJob
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import nemoterm_debug as api

def digest(raw):return hashlib.sha256(raw).hexdigest()

def trial(out,exe,font,trace,replay_sha,physical,rec):
    profile='image-keys-'+uuid.uuid4().hex;key='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
    report=out/'events.json';control=out/'control.json';out.mkdir()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,key) as k:
        for name,value in [('NemoRenderer',0),('CloseOnExit',1),('WarnOnClose',0)]:winreg.SetValueEx(k,name,0,winreg.REG_DWORD,value)
    try:
        with OwnedJob() as job:
            proc=job.spawn([str(exe),'-load',profile,'--automation','--cols','100','--rows','30','--font',font,'-e',sys.executable,str(ROOT/'tests/win32_input_fixture.py'),str(report),str(control)],env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
            inst=wait_for(lambda:next(iter(api.discover(proc.pid)),None),timeout=25);sess,=inst['sessions'];endpoint=inst['endpoint'];seat=sess['id'];assert sess['renderer']==0
            rec['session']=sess;rec['replayed_bytes_sha256']=replay_sha;rec['events']={}
            desk=DesktopInput(proc.pid,sess['window'],sess['hwnd'],rec.setdefault('desktop',{})) if physical else None
            clip=SavedClipboard(sess['hwnd'])
            try:
                write_snapshot(control,dict(phase='prelude',sequence='',replay=trace and str(trace)));wait_for(lambda:read_snapshot(report).get('phase')=='prelude');time.sleep(.5)
                for bind,mods in [('ctrl-v',2),('ctrl-shift-v',3)]:
                    write_snapshot(control,dict(phase=bind,sequence='\r\nKEYBOUNDARY '+bind+'\r\n'))
                    wait_for(lambda:read_snapshot(report).get('phase')==bind and 'KEYBOUNDARY '+bind in api.request(endpoint,'text',seat));put_bitmap(sess['hwnd'])
                    if desk:desk.chord(*((0x11,0x10) if mods==3 else (0x11,)),86)
                    else:api.request(endpoint,'key',seat,struct.pack('<II',86,mods))
                    time.sleep(.8);row=read_snapshot(report);assert row.get('phase')==bind
                    rec['events'][bind]=row['events']
            finally:
                if desk:desk.restore()
                clip.restore();write_snapshot(control,dict(stop=True))
            assert proc.wait(timeout=10)==0;rec['cleanup']=job.finish();assert not rec['cleanup']['terminated_remaining']
            for bind,events in rec['events'].items():
                # Store whether the logical Windows shortcut was actually present.
                # An ESC/CSI sequence of individual key records is not this event.
                hits=[e for e in events if e.get('type')=='key' and e['down'] and e['vk']==86 and e['control']&12]
                rec.setdefault('ctrl_v_keydowns',{})[bind]=len(hits)
            assert all(n==1 for n in rec['ctrl_v_keydowns'].values()),rec['ctrl_v_keydowns']
    finally:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,key)

def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise RuntimeError('Hosted only')
    exe=Path(os.environ['NEMOTERM_TEST_EXE']).resolve(strict=True);out=ROOT/'build/image-key-records';out.mkdir(parents=True,exist_ok=False)
    font=os.environ['NEMOTERM_TEST_FONT']
    root=ROOT/'tests/fixtures/codex-image-keys';meta=json.loads((root/'source.json').read_bytes());summary=dict(exe_sha256=digest(exe.read_bytes()),source=meta,font=font,cases={})
    for source in ['none',*meta['inputs']]:
        trace=root/(source+'.vt') if source!='none' else None;sha=digest(trace.read_bytes()) if trace else None
        if trace:assert sha==meta['inputs'][source]['sha256']
        for physical in (False,True):
            name=source+'-'+('system' if physical else 'api');rec=summary['cases'][name]=dict(passed=False)
            try:trial(out/name,exe,font,trace,sha,physical,rec);rec['passed']=True
            except Exception:rec['error']=traceback.format_exc()
            write_snapshot(out/'summary.json',summary)
    return int(not all(row['passed'] for row in summary['cases'].values()))
if __name__=='__main__':sys.exit(main())
