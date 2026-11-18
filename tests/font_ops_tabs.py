"""An app-selected font must not follow a duplicated tab or change its saved profile."""
import argparse, hashlib, json, os, re, struct, subprocess, sys, tempfile, traceback, winreg
from pathlib import Path
from native_test_utils import root, c, w, u, wait_for, wait_snapshot, read_snapshot, write_snapshot
from protocol_oracle_window import saved_profile
from owned_job import OwnedJob
sys.path.insert(0,str(root/'tools'))
import nemoterm_debug as api


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    ap=argparse.ArgumentParser();ap.add_argument('--renderer',choices=('gdi','directx'),required=True);ren=ap.parse_args().renderer
    exe=Path(os.environ['NEMOTERM_TEST_EXE']);base=os.environ['NEMOTERM_TEST_FONT'];alt='Consolas';st='\x1b\\';osc='\x1b]50;'
    out=root/'build/font-ops/tabs.json';out.parent.mkdir(parents=True,exist_ok=True)
    d=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),renderer=ren,observations=[],completed=False)
    cfg=dict(Font=base,NemoTabs=1,NemoRenderer=0 if ren=='gdi' else 2,NemoAllowGetFont=1,NemoAllowSetFont=1,
             WarnOnClose=0,FontHeight=12,CloseOnExit=1)
    u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
    try:
        with saved_profile(cfg) as profile, tempfile.TemporaryDirectory() as tmp, OwnedJob() as job:
            folder=Path(tmp);p=job.spawn([str(exe),*profile,'--tabs','--automation','--cols','80','--rows','24','-e',sys.executable,
                str(root/'tests/session_fixture.py'),str(folder),'180'],env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1'),creationflags=subprocess.CREATE_NO_WINDOW)
            known=set()
            def child():
                rr=wait_for(lambda:next((x for x in folder.glob('*.report.json') if x not in known and 'hex' in read_snapshot(x)),None));known.add(rr);return rr
            def set_or_query(rr,label,face,expect):
                ctl=folder/(rr.name.removesuffix('.report.json')+'.control.json');write_snapshot(ctl,dict(phase=label,preserve_mouse=True,
                    sequence=(osc+face+st if face else '')+osc+'?'+st+'\x1b[16t\x1b[5n'))
                data=wait_snapshot(lambda:read_snapshot(rr),lambda v:v.get('phase')==label and v.get('hex','').endswith('1b5b306e'))
                raw=bytes.fromhex(data['hex']);d['observations'].append(dict(label=label,child=rr.name,wire=raw.hex(),expected_face=expect))
                response=re.fullmatch(rb'\x1b\]50;([^\x1b]+)\x1b\\\x1b\[6;(\d+);(\d+)t\x1b\[0n',raw);assert response and response[1]==expect.encode(),(label,raw,expect)
                return [int(response[2]),int(response[3])]
            one=child();inst=wait_for(lambda:next(iter(api.discover(p.pid)),None));endpoint=inst['endpoint'];first,=inst['sessions']
            before=set_or_query(one,'profile',None,base);other_size=set_or_query(one,'first-change',alt,alt);assert before!=other_size
            assert u.PostMessageW(first['hwnd'],0x111,0x30,0)  # Duplicate Tab, with its original command.
            two=child();second=wait_for(lambda:next((s for s in api.request(endpoint)['sessions'] if s['active'] and s['id']!=first['id']),None))
            assert second['window']==first['window'];d['seats']=[first,second]
            assert set_or_query(two,'duplicate-inherits-profile',None,base)==before
            assert set_or_query(one,'inactive-still-changed',None,alt)==other_size
            assert set_or_query(one,'inactive-restore',base,base)==before
            assert set_or_query(one,'inactive-change',alt,alt)==other_size
            assert set_or_query(two,'active-remains-original',None,base)==before
            assert next(s for s in api.request(endpoint)['sessions'] if s['active'])['id']==second['id']
            api.request(endpoint,'key',second['id'],struct.pack('<II',9,2));wait_for(lambda:any(s['active'] and s['id']==first['id'] for s in api.request(endpoint)['sessions']))
            assert set_or_query(one,'reactivated',None,alt)==other_size
            d['actual_renderer']=int(u.GetPropW(first['hwnd'],'NemotermRenderer') or 0);assert d['actual_renderer']==(1 if ren=='gdi' else 3)
            for action in ('save','revoke'):
                driver=job.spawn(['powershell.exe','-NoProfile','-File',str(root/'tests/font_ops_settings.ps1'),
                    '-TargetProcess',str(p.pid),'-TargetWindow',str(first['hwnd']),'-Action',action],creationflags=subprocess.CREATE_NO_WINDOW)
                assert driver.wait(timeout=65)==0,action
                after=alt if action=='save' else base
                assert set_or_query(one,'settings-'+action,None,after)==(other_size if action=='save' else before)
            assert set_or_query(one,'revoked-write',alt,base)==before
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Software\\Nemo\\Nemoterm\\Sessions\\'+profile[1]) as key:
                d['saved_font']=winreg.QueryValueEx(key,'Font')[0];assert d['saved_font']==base
                assert winreg.QueryValueEx(key,'NemoAllowGetFont')[0]==1 and winreg.QueryValueEx(key,'NemoAllowSetFont')[0]==0
            for rr in [one,two]:write_snapshot(folder/(rr.name.removesuffix('.report.json')+'.control.json'),dict(stop=True))
            assert p.wait(timeout=15)==0;d['cleanup']=job.finish();assert not d['cleanup']['terminated_remaining'];d['completed']=True
    except Exception:d['error']=traceback.format_exc();raise
    finally:write_snapshot(out,d)

if __name__=='__main__':main()
