"""Periodic diagnostic stacks from a Python thread, without a native watchdog.

CPython 3.12's dump_traceback_later can race freed frames while walking them
without the GIL (python/cpython#140815). Calling dump_traceback from a normal
Python thread avoids that race on the GIL-enabled fixture interpreters.
This observer cannot run while native code holds the GIL indefinitely; external
job deadlines remain responsible for stopping a hung fixture.
"""
import atexit
import faulthandler
import math
import sys
import threading


def start_periodic_tracebacks(seconds, file=None):
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('Traceback interval must be finite and positive')
    output = sys.stderr if file is None else file
    stopped = threading.Event()

    def observe():
        while not stopped.wait(seconds):
            faulthandler.dump_traceback(file=output, all_threads=True)

    worker = threading.Thread(target=observe, name='fixture-traceback', daemon=True)

    def stop():
        stopped.set()
        worker.join(timeout=1)

    atexit.register(stop)
    worker.start()
    return stop
