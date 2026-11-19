"""Replay upstream byte streams through a native ConPTY child on a hosted desktop."""
import hashlib,json,os,re,zipfile
from pathlib import Path
from column_mode_cases import C,PAINT,PROBE,stages
from native_test_utils import c,w,u,capture,wait_for,time,root
from protocol_oracle_window import run


def size(hwnd):
    r=w.RECT();assert u.GetClientRect(hwnd,c.byref(r));return r.right,r.bottom


def main():
    if os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise RuntimeError('GitHub-hosted runner required')
    gpu=os.environ['RENDERER'];renderer={'gdi':1,'directx':3}[gpu];font=os.environ['NEMOTERM_TEST_FONT']
    u.GetPropW.argtypes=[w.HWND,w.LPCWSTR];u.GetPropW.restype=w.HANDLE
    path=root/'testdata/upstream/xterm412-column-modes-profiles.zip';report={'reference_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'product_sha256':hashlib.sha256(Path(os.environ['NEMOTERM_TEST_EXE']).read_bytes()).hexdigest(),'profiles':{}}
    assert report['reference_sha256']=='1c1aff498bc0559194d2e1880c1d7344990d03f989a6b05055b6de76bd46b495'
    rows=[];local=[]
    with zipfile.ZipFile(path) as z:
        for profile in ('enabled','disabled','level4','explicit-80','explicit-off','explicit-level4','local-deny'):
            name='column-mode-'+gpu+'-'+profile
            seq=stages(profile) if profile!='local-deny' else {'before':C+'?40;95h'+PAINT+PROBE,'attempt':C+'?3h'+PROBE,'clear-attempt':C+'?95l'+C+'?3l'+PROBE}
            src={} if profile=='local-deny' else json.loads(z.read('column-modes/'+profile+'.json'))['cases']
            if src:assert list(seq)==list(src) and all(seq[k]==v['sequence'] for k,v in src.items())
            points=report['profiles'][profile]={}
            def body(hwnd,phase,current):
                assert u.GetPropW(hwnd,'NemotermRenderer')==renderer
                base=size(hwnd);cw=(base[0]-2)//80;ch=(base[1]-2)//24
                assert base==(2+cw*80,2+ch*24),(base,cw,ch)
                for key,s in seq.items():
                    raw=phase(key,s,None);client=size(hwnd);state=current();cols=(client[0]-2)//cw
                    m=re.search(rb'\x1b\[8;(\d+);(\d+)t',raw);assert m,(key,raw)
                    cells=[int(n,16) for n in re.findall(rb'!~([0-9A-F]{4})',raw)];assert len(cells)==4
                    geom=client==(2+cw*int(m[2]),2+ch*int(m[1]));o=points[key]=dict(wire=raw.hex(),cells=cells,client=client,cell=[cw,ch],reported_cols=int(m[2]),child_cols=state.get('columns'),geometry_matches=geom)
                    if src:o['expected']=src[key]['reply_hex'];o['matches']=raw.hex()==o['expected'];rows.append(o['matches'] and geom)
                    else:local.append(cols==80 and geom and cells==[65,0x4e2d,0,90] and b'\x1b[7;11R' in raw and b'\x1b[?3;4$y' in raw and b'\x1b[?40;4$y' in raw)
                    if gpu=='gdi' and key in ('paint','keep-widen','keep-narrow','same-width-clear','before','clear-attempt'):
                        # Check the four glyph-bearing cells independently of the reported characters.
                        def ink(pixels):
                            return [len(set(b''.join(pixels[3*((1+ch+j)*client[0]+1+x*cw):3*((1+ch+j)*client[0]+1+(x+1)*cw)] for j in range(ch))))>1 for x in range(2,6)]
                        expected=[n!=0x20 for n in cells];until=time.monotonic()+1
                        while ink(capture(hwnd,return_pixels=True))!=expected and time.monotonic()<until:time.sleep(.05)
                        o['ink']=ink(capture(hwnd,name+'-'+key+'.png',return_pixels=True));o['ink_matches']=o['ink']==expected
                return {'actual_renderer':renderer,'base':base}
            run(name,[],exercise=body,barrier=(C+'5n',b'\x1b[0n'),font=font,profile=dict(NemoTabs=1,NemoRenderer=renderer-1,NemoColumnModeStart=2 if profile.startswith('explicit') else 1,NoRemoteResize=int(profile=='local-deny'),NemoAllowChecksum=1,UTF8linedraw=1,FontHeight=8,WarnOnClose=0,LockSize=0))
    report['strict_matches']=sum(rows);report['strict_total']=len(rows);report['local_policy']=local
    (root/'research'/('column-mode-'+gpu+'-summary.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    assert len(rows)==132 and len(local)==3 and all(rows) and all(local) and all(o.get('ink_matches',True) for v in report['profiles'].values() for o in v.values()),(sum(rows),len(rows),local)

def cli():
    if os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise RuntimeError('GitHub-hosted runner required')
    gpu=os.environ['RENDERER']; font=os.environ['NEMOTERM_TEST_FONT']
    # Match the upstream startup reports at a real 80x24 geometry. Save the
    # opposite preference in the profile so a parser that ignores CLI fails.
    with zipfile.ZipFile(root/'testdata/upstream/xterm412-column-modes-profiles.zip') as z:
        for arg,opposite,ref in [('-132',2,'enabled'),('+132',1,'explicit-off')]:
            expected=bytes.fromhex(json.loads(z.read('column-modes/'+ref+'.json'))['cases']['initial']['reply_hex'])
            run('column-mode-'+gpu+'-cli-'+ref,[('initial',PROBE,expected)],
                barrier=(C+'5n',b'\x1b[0n'),font=font,frontend_args=[arg],
                profile=dict(NemoTabs=1,NemoRenderer=0 if gpu=='gdi' else 2,
                             NemoColumnModeStart=opposite,NemoAllowChecksum=1,FontHeight=8,WarnOnClose=0))


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--cli',action='store_true')
    if ap.parse_args().cli:cli()
    else:main()
