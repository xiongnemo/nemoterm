"""Validate post-failure metadata against retained private-job identities."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from job_failure_snapshot import capture_job_failure
from owned_job import OwnedJob, k


class FailureSnapshotTests(unittest.TestCase):
    def test_owned_metadata_and_foreign_job_rejection(self):
        with tempfile.TemporaryDirectory(prefix='nemoterm-job-snapshot-') as temporary:
            with OwnedJob() as job, OwnedJob() as other:
                process = job.spawn([sys.executable, '-c',
                    'import time; print("ready",flush=True); time.sleep(30)', 'owned-metadata-marker'],
                    stdout=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                handles = []
                try:
                    self.assertEqual(process.stdout.readline().strip(), 'ready')
                    handles = job.member_handles()
                    result = capture_job_failure(job, handles, Path(temporary)/'owned')
                    record = next(r for r in result['processes'] if r['pid'] == process.pid)
                    self.assertNotIn('error', record)
                    self.assertIn('owned-metadata-marker', record['command_line'])
                    self.assertGreater(record['created'], 0)
                    self.assertNotIn('observation_error', record['process_before_cleanup'])
                    self.assertGreater(len(record['process_before_cleanup']['threads']['threads']), 0)
                    rejected = capture_job_failure(other, handles, Path(temporary)/'wrong-job')
                    for row in rejected['processes']:
                        self.assertIn('error', row)
                        self.assertNotIn('command_line', row)
                        self.assertNotIn('process_before_cleanup', row)
                    self.assertIsNone(process.poll())
                finally:
                    for handle in handles:
                        k.CloseHandle(handle)
                    job.finish(grace=0)
                    process.wait(timeout=5)
                    process.stdout.close()


if __name__ == '__main__':
    unittest.main()
