"""Record current native cell widths; this observer is not a conformance pass."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'tests'))
from native_test_utils import *
from owned_job import OwnedJob
import re
import uuid
import winreg

exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
cases=[('ascii','AB'),('combining','e\u0301'),('cjk','\u4e2d'),
       ('emoji','\U0001f642'),('skin-tone','\U0001f44d\U0001f3fd'),
       ('zwj-profession','\U0001f469\u200d\U0001f4bb'),
       ('zwj-family','\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466'),
       ('flag','\U0001f1e6\U0001f1fa'),('keycap','1\ufe0f\u20e3'),
       ('emoji-heart','\u2764\ufe0f'),('text-heart','\u2764\ufe0e'),
       ('hangul-jamo','\u1100\u1161\u11a8')]
profile='grapheme-observation-'+uuid.uuid4().hex
keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
              font='SarasaTermSC Nerd Font Light',observations=[],conformance_claim=False)
with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as registry:
    for name,value in dict(WarnOnClose=0,CloseOnExit=1,NemoRenderer=0).items():
        winreg.SetValueEx(registry,name,0,winreg.REG_DWORD,value)
try:
    with tempfile.TemporaryDirectory(prefix='nemoterm-grapheme-observer-') as tmp,OwnedJob() as job:
        report,control=Path(tmp)/'report',Path(tmp)/'control'
        process=job.spawn([str(exe),'-load',profile,'--cols','80','--rows','24',
            '--font',evidence['font'],'-e',sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control)],
            env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1'),
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            hwnd=wait_for(lambda:find_window(process.pid));wait_for(lambda:read_snapshot(report))
            for name,text in cases:
                write_snapshot(control,dict(phase=name,sequence='\x1b[2J\x1b[H'+text+'\x1b[6n\x1b[5n'))
                value=wait_snapshot(lambda:read_snapshot(report),lambda v:
                    v.get('phase')==name and bytes.fromhex(v.get('hex','')).endswith(b'\x1b[0n'))
                match=re.search(rb'\x1b\[(\d+);(\d+)R',bytes.fromhex(value['hex']));assert match,value
                row,col=map(int,match.groups());assert row==1
                evidence['observations'].append(dict(name=name,text=text,
                    scalars=[f'U+{ord(ch):04X}' for ch in text],columns=col-1))
            gallery='\x1b[?25l\x1b[2J\x1b[H'+''.join(f'{name:<16}{text}\r\n' for name,text in cases)
            write_snapshot(control,dict(phase='gallery',sequence=gallery+'\x1b[5n'))
            wait_snapshot(lambda:read_snapshot(report),lambda v:
                v.get('phase')=='gallery' and bytes.fromhex(v.get('hex','')).endswith(b'\x1b[0n'))
            capture(hwnd,'grapheme-baseline.png')
            write_snapshot(control,dict(stop=True));assert process.wait(timeout=10)==0
            evidence['owned_job_cleanup']=job.finish(grace=5)
            assert not evidence['owned_job_cleanup']['terminated_remaining']
        finally:
            evidence.setdefault('owned_job_cleanup',job.finish(grace=0))
finally:
    if sys.exc_info()[0]:evidence['error']=repr(sys.exc_info()[1])
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
    (root/'research/grapheme-baseline.json').write_text(json.dumps(evidence,indent=2))
print([(v['name'],v['columns']) for v in evidence['observations']])
