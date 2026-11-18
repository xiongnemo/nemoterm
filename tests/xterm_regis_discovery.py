"""Record an independently built XTerm's actual ReGIS discovery replies."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
from xterm_state_oracle import run_cases

ARCHIVE=Path('research/regis-repaint-reference.zip')
PIN='ca9165f9d14cb8ef67840a3c46063fde3d4f9dc104ac58086bc9b125c79fac4f'
EXECUTABLE='0fc7b2f29c3777794701202c8d788a0e3392dcaba39662c14cac872a86829b84'
CSI='\x1b['

if __name__=='__main__':
    import os
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise SystemExit('Capture on a GitHub-hosted runner')
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);args=parser.parse_args()
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=True)
    assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()==PIN
    with ZipFile(ARCHIVE) as z:
        data=z.read('xterm');assert hashlib.sha256(data).hexdigest()==EXECUTABLE
        assert b'#define OPT_REGIS_GRAPHICS 1' in z.read('defines.txt').splitlines()
    executable=root/'xterm';executable.write_bytes(data);executable.chmod(0o755)
    cases={'identity':CSI+'c'}
    for action in (0,1,2,3,4,5,99):
        params=f'3;{action};0';cases[params]=CSI+'?1;3;256S'+CSI+'?'+params+'S'+CSI+'?1;1;0S'
    cases['invalid-arity']=CSI+'?3;1S'+CSI+'?3;1;0;0S'
    cases['after-draw']='\x1bP1pS(E)P[11,13]R(P)\x1b\\'+CSI+'?3;1;0S'
    cases['after-reset']='\x1bc'+CSI+'?3;1;0S'
    for size in ('160x120','800x480'):
        output=root/(size+'.json');run_cases(str(executable),str(output),cases,
            ['-ti','vt340','-xrm','*decGraphicsID:340','-xrm','*regisScreenSize:'+size,'-xrm','*maxGraphicSize:'+size],raw_replies=True)
        report=json.loads(output.read_text());assert report['executable_sha256']==EXECUTABLE and set(report['cases'])==set(cases)
        assert '3' in report['cases']['identity']['reply'].removeprefix(CSI+'?').removesuffix('c').split(';')[1:]
        assert report['cases']['after-reset']['reply']==CSI+'?3;0;'+size.replace('x',';')+'S'
