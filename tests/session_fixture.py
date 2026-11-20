"""Independent VT mailboxes; stress runs distinguish repeated uses of a PID."""
import os
from pathlib import Path
import runpy
import sys
import time
from fixture_io import write_snapshot

directory = Path(sys.argv[1])
seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 300
if not 1 <= seconds <= 1800:
    raise ValueError('Session fixture lifetime must be between 1 and 1800 seconds')
pid = os.getpid()
# Windows can recycle a retired child PID during one create/close loop.
# Keep older callers' paths; resource tests opt into a fresh mailbox per launch.
mailbox = f'{pid}-{os.urandom(12).hex()}' if sys.argv[3:] == ['--unique-mailbox'] else str(pid)
write_snapshot(directory/f'{mailbox}.launch.json',
               dict(pid=pid, mailbox=mailbox, parent=os.getppid(), cwd=os.getcwd(), lifetime_seconds=seconds))
sys.argv = [str(Path(__file__).with_name('mouse_fixture.py')),
            str(directory/f'{mailbox}.report.json'), str(directory/f'{mailbox}.control.json'), str(seconds)]
started = time.monotonic()
exit_record = dict(pid=pid, mailbox=mailbox, lifetime_seconds=seconds)
try:
    state = runpy.run_path(sys.argv[0], run_name='__main__')
    exit_record.update(reason='control-stop' if state['request'].get('stop') else 'deadline',
                       last_phase=state['phase'],
                       deadline_reached=time.monotonic() >= state['deadline'])
except BaseException as error:
    exit_record.update(reason='exception', error=repr(error))
    raise
finally:
    exit_record['elapsed_seconds'] = time.monotonic()-started
    write_snapshot(directory/f'{mailbox}.exit.json', exit_record)
