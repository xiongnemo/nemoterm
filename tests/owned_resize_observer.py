"""CI-only external snapshots while an owned synchronous resize is outstanding.

This is an opt-in diagnostic, never a memory-acceptance run. Two observations
at 30 and 60 seconds retain CPU times and small dumps without aborting,
retrying or replacing MoveWindow. The caller's existing watchdog is unchanged.
"""
from pathlib import Path
import threading
import time
from fixture_io import write_snapshot
from native_failure_dump import capture_owned_failure_dump
from thread_snapshot import OwnedThreadSnapshot


class OwnedResizeObserver:
    def __init__(self, process, job, helper, destination):
        self.process, self.job = process, job
        self.helper = Path(helper).resolve(strict=True)
        self.destination = Path(destination)
        self.destination.mkdir(parents=True, exist_ok=False)
        self.threads = OwnedThreadSnapshot(process, job)
        self.records = []

    def call(self, function, *arguments):
        index = len(self.records)
        record = dict(index=index, pid=self.process.pid, diagnostic_only=True,
                      arguments=list(arguments), returned=False, samples=[])
        self.records.append(record)
        path = self.destination/f'resize-{index}.json'
        done = threading.Event()
        started = time.monotonic()

        def save():
            record['seconds'] = time.monotonic()-started
            write_snapshot(path, record)

        record['threads_before'] = self.threads.snapshot('before-resize')
        save()

        def observe():
            for threshold in (30, 60):
                if done.wait(max(0, started+threshold-time.monotonic())):
                    return
                sample = dict(threshold_seconds=threshold,
                              seconds=time.monotonic()-started)
                record['samples'].append(sample)
                try:
                    sample['threads'] = self.threads.snapshot('resize-outstanding')
                    save()
                    sample['capture'] = capture_owned_failure_dump(
                        self.helper, self.process, self.job,
                        self.destination/f'resize-{index}-{threshold}')
                    # A return concurrent with capture is not a hung-thread
                    # snapshot. Keep that uncertainty in the raw record.
                    sample['resize_returned_during_capture'] = done.is_set()
                except Exception as error:
                    sample['error'] = repr(error)
                save()

        worker = threading.Thread(target=observe, daemon=True)
        worker.start()
        returned = False
        try:
            result = function(*arguments)
            returned = True
            return result
        finally:
            done.set()
            worker.join(timeout=20)
            if worker.is_alive():
                raise RuntimeError('Resize observer did not finish its bounded helper')
            record['returned'] = returned
            if returned:
                record['return_value'] = result
            record['threads_after'] = self.threads.snapshot('after-resize')
            save()
