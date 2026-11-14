"""Exercise periodic stacks during frame churn, shutdown and a failing child."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory(prefix='fixture-traceback-') as directory:
    folder = Path(directory)
    source = folder/'child.py'
    source.write_text('''
import json,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from fixture_traceback import start_periodic_tracebacks
stop=start_periodic_tracebacks(.005)
def frame_churn():
    return json.loads(Path(sys.argv[2]).read_text())
deadline=time.monotonic()+1
while time.monotonic()<deadline:
    assert frame_churn()=={'fixture':True}
stop()
print('stopped',flush=True)
time.sleep(.05)
raise SystemExit(int(sys.argv[3]))
''', encoding='utf-8')
    data=folder/'data.json';data.write_text('{"fixture":true}')
    for expected in (0,0,7):
        run=subprocess.run([sys.executable,str(source),str(Path(__file__).resolve().parent),
                            str(data),str(expected)],capture_output=True,text=True,timeout=10)
        assert run.returncode==expected,(run.returncode,run.stdout,run.stderr[-2000:])
        assert run.stdout=='stopped\n',run.stdout
        assert run.stderr.count('frame_churn')>=2,run.stderr
        assert 'observe' in run.stderr,run.stderr
print('Periodic traceback: frame churn, natural stop and failure exit passed')
