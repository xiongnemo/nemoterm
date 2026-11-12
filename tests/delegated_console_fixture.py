"""A console launcher exits while its attached child remains interactive."""
from fixture_io import write_snapshot
import os
from pathlib import Path
import subprocess
import sys
import time

report, stop = map(Path, sys.argv[1:3])
if len(sys.argv) == 3:
    child = subprocess.Popen([sys.executable, __file__, str(report), str(stop), str(os.getpid())])
    # Popen has established the inherited console reference before we exit.
    sys.exit(0)
time.sleep(.8)
print('DELEGATED_CONSOLE_READY', flush=True)
write_snapshot(report, dict(launcher=int(sys.argv[3]), child=os.getpid()))
deadline = time.monotonic() + 15
while not stop.exists() and time.monotonic() < deadline:
    time.sleep(.02)
print('DELEGATED_CONSOLE_DONE', flush=True)
