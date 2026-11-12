"""Owned ConPTY child: report launch directory, then use the VT mailbox."""
import os
from pathlib import Path
import runpy
import sys
from fixture_io import write_snapshot

directory = Path(sys.argv[1])
pid = os.getpid()
write_snapshot(directory / f"{pid}.launch.json",
               dict(pid=pid, parent=os.getppid(), cwd=os.getcwd()))
sys.argv = [str(Path(__file__).with_name("mouse_fixture.py")),
            str(directory / f"{pid}.report.json"), str(directory / f"{pid}.control.json")]
runpy.run_path(sys.argv[0], run_name="__main__")
