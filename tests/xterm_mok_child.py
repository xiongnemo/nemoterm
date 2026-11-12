"""Raw PTY child of the isolated xterm reference harness."""
import json, os, select, sys, termios, time, tty
from pathlib import Path
report, control = map(Path, sys.argv[1:3])
def write(value):
    temporary = report.with_suffix('.tmp')
    temporary.write_text(json.dumps(value)); temporary.replace(report)
tty.setraw(0)
phase, data = None, b''
deadline = time.monotonic()+180
write({'phase':phase, 'hex':''})
while time.monotonic()<deadline:
    try: command=json.loads(control.read_text())
    except (FileNotFoundError, ValueError): command={}
    if command.get('stop'): break
    if command.get('phase')!=phase:
        phase=command['phase']; data=b''
        os.write(1,command.get('sequence','').encode())
        write({'phase':phase,'hex':''})
    if select.select([0],[],[],.005)[0]:
        data+=os.read(0,4096)
        write({'phase':phase,'hex':data.hex()})
