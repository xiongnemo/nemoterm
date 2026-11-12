"""Real process lifecycle checks without terminal windows or desktop input."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from owned_job import OwnedJob, c, k, w


class OwnedJobTests(unittest.TestCase):
    def test_late_descendants_are_drained_and_unrelated_process_survives(self):
        outside = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            with tempfile.TemporaryDirectory(prefix='nemoterm-job-test-') as tmp:
                report = Path(tmp)/'child.json'
                code = ('import subprocess,sys,time,json; from pathlib import Path; '
                    'time.sleep(.1); p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"],creationflags=subprocess.CREATE_NO_WINDOW); '
                    'Path(sys.argv[1]).write_text(json.dumps({"child":p.pid})); time.sleep(30)')
                with OwnedJob() as job:
                    process = job.spawn([sys.executable, '-c', code, str(report)], cwd=tmp,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
                    child = None
                    try:
                        deadline = time.monotonic()+8
                        while not report.exists() and time.monotonic() < deadline:
                            time.sleep(.02)
                        child_pid = json.loads(report.read_text())['child']
                        child = k.OpenProcess(0x101000, False, child_pid)
                        self.assertTrue(child)
                        member = w.BOOL()
                        self.assertTrue(k.IsProcessInJob(child, job.handle, c.byref(member)))
                        self.assertTrue(member.value)
                        # Windows can also create hidden console hosts in the job.
                        self.assertGreaterEqual(job.accounting()['active'], 2)
                        process.terminate(); process.wait(timeout=5)
                        self.assertEqual(k.WaitForSingleObject(child, 0), 258)
                        cleanup = job.finish(grace=0)
                        self.assertTrue(cleanup['terminated_remaining'])
                        self.assertEqual(cleanup['after']['active'], 0)
                        self.assertGreaterEqual(cleanup['after']['total'], 2)
                        self.assertEqual(k.WaitForSingleObject(child, 0), 0)
                    finally:
                        job.finish(grace=0)
                        process.wait(timeout=5)
                        if child:
                            k.CloseHandle(child)
                self.assertIsNone(outside.poll())
            self.assertFalse(Path(tmp).exists())
        finally:
            outside.terminate(); outside.wait(timeout=5)

    def test_natural_exit_needs_no_termination(self):
        with OwnedJob() as job:
            process = job.spawn([sys.executable, '-c', 'pass'], creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(process.wait(timeout=5), 0)
            self.assertFalse(job.finish()['terminated_remaining'])


if __name__ == '__main__':
    unittest.main()
