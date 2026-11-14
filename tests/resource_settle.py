"""Bounded polling for native resource checks; never discards observations.

Process-wide initialization precedes the baseline. Post-close counts must return
to the original allowances and stay there; a deadline is a failure, not a new
baseline. The caller retains the record even when this module raises.
"""
import time

ALLOWANCES = {'handles': 6, 'gdi': 3, 'user': 2}


def startup(sample, record, *, clock=time.monotonic, sleep=time.sleep,
            minimum=3.0, quiet=2.0, timeout=10.0, interval=0.05):
    started = clock()
    unchanged = started
    previous = None
    while True:
        value = sample()
        now = clock()
        signature = tuple(value[k] for k in ALLOWANCES)
        if signature != previous:
            unchanged, previous = now, signature
        record.append(dict(seconds=now-started, quiet_seconds=now-unchanged,
                           sample=value))
        # Check the deadline first: a slow observer cannot produce a late pass.
        assert now-started <= timeout, 'Startup resource baseline did not settle'
        if now-started >= minimum and now-unchanged >= quiet:
            return value
        sleep(min(interval, max(0.0, timeout-(now-started))))


def after_close(sample, baseline, record, *, clock=time.monotonic,
                sleep=time.sleep, quiet=0.25, timeout=2.0, interval=0.05):
    started = clock()
    within_since = None
    while True:
        value = sample()
        now = clock()
        within = all(value[k] <= baseline[k]+limit
                     for k, limit in ALLOWANCES.items())
        if not within:
            within_since = None
        elif within_since is None:
            within_since = now
        record.append(dict(seconds=now-started, within=within,
                           quiet_seconds=now-within_since if within else 0.0,
                           sample=value))
        assert now-started <= timeout, 'Closed-tab resources did not return to baseline'
        if within and now-within_since >= quiet:
            return value
        sleep(min(interval, max(0.0, timeout-(now-started))))
