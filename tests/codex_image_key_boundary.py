"""Trace only the diagnostic console's keyboard records after replaying Codex output."""
import hashlib,json,os,struct,subprocess,sys,time,traceback,uuid,winreg
from pathlib import Path
from agent_clipboard_fixture import put_bitmap
from clipboard_test_utils import SavedClipboard
from fixture_io import read_snapshot,wait_snapshot,write_snapshot
from hosted_gesture_input import DesktopInput
from native_test_utils import wait_for
from owned_job import OwnedJob
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import nemoterm_debug as api

def digest(raw):return hashlib.sha256(raw).hexdigest()

# vk, down, scan code, Unicode character, control state and repeat count, in
# native input order (the two paste bindings deliver the same logical Ctrl+V).
KEY_FIELDS=('vk','down','scan','character','control','repeat')
EXPECTED_KEYS=[(17,1,29,0,8,1),(86,1,47,22,8,1),(86,0,47,22,8,1),(17,0,29,0,0,1)]

def trial(out,exe,font,trace,replay_sha,physical,rec):
    profile='image-keys-'+uuid.uuid4().hex;key='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
    report=out/'events.json';control=out/'control.json';out.mkdir()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,key) as k:
        for name,value in [('NemoRenderer',0),('CloseOnExit',1),('WarnOnClose',0)]:winreg.SetValueEx(k,name,0,winreg.REG_DWORD,value)
    try:
        with OwnedJob() as job:
            proc=job.spawn([str(exe),'-load',profile,'--automation','--cols','100','--rows','30','--font',font,'-e',sys.executable,str(ROOT/'tests/win32_input_fixture.py'),str(report),str(control),'--timestamp-records'],env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
            inst=wait_for(lambda:next(iter(api.discover(proc.pid)),None),timeout=25);sess,=inst['sessions'];endpoint=inst['endpoint'];seat=sess['id'];assert sess['renderer']==0
            rec['session']=sess;rec['replayed_bytes_sha256']=replay_sha;rec['events']={}
            desk=DesktopInput(proc.pid,sess['window'],sess['hwnd'],rec.setdefault('desktop',{})) if physical else None
            clip=SavedClipboard(sess['hwnd'])
            try:
                write_snapshot(control,dict(phase='prelude',sequence='',replay=trace and str(trace)));wait_for(lambda:read_snapshot(report).get('phase')=='prelude');time.sleep(.5)
                for bind,mods in [('ctrl-v',2),('ctrl-shift-v',3)]:
                    write_snapshot(control,dict(phase=bind,sequence='\r\nKEYBOUNDARY '+bind+'\r\n'))
                    wait_for(lambda:read_snapshot(report).get('phase')==bind and 'KEYBOUNDARY '+bind in api.request(endpoint,'text',seat));put_bitmap(sess['hwnd'])
                    sent_ns=time.monotonic_ns()
                    if desk:desk.chord(*((0x11,0x10) if mods==3 else (0x11,)),86)
                    else:api.request(endpoint,'key',seat,struct.pack('<II',86,mods))
                    cutoff=time.monotonic_ns()+800_000_000
                    time.sleep(.8)
                    # The controller may briefly fail to open a rotating mailbox.
                    # Wait only for publication; late keyboard input must still fail.
                    row=wait_snapshot(lambda:read_snapshot(report),
                                      lambda v:v.get('error') or (v.get('phase')==bind and v.get('sample_ns',0)>=cutoff),timeout=2)
                    assert not row.get('error'),row
                    rec['events'][bind]=row['events']
                    rec.setdefault('observation',{})[bind]=dict(sent_ns=sent_ns,cutoff_ns=cutoff,sample_ns=row['sample_ns'])
            finally:
                if desk:desk.restore()
                clip.restore();write_snapshot(control,dict(stop=True))
            assert proc.wait(timeout=10)==0;rec['cleanup']=job.finish();assert not rec['cleanup']['terminated_remaining']
            for bind,events in rec['events'].items():
                # Store whether the logical Windows shortcut was actually present.
                # An ESC/CSI sequence of individual key records is not this event.
                hits=[e for e in events if e.get('type')=='key' and e['down'] and e['vk']==86 and e['control']&12]
                rec.setdefault('ctrl_v_keydowns',{})[bind]=len(hits)
            for bind,events in rec['events'].items():
                keys=[e for e in events if e['type']=='key']
                observed=[tuple(e[k] for k in KEY_FIELDS) for e in keys]
                assert observed==EXPECTED_KEYS,(bind,observed)
                window=rec['observation'][bind]
                assert all(window['sent_ns']<=e['observed_ns']<=window['cutoff_ns'] for e in keys),(bind,window,keys)
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
