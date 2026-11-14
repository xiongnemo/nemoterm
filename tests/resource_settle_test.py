"""Deterministic timing and persistent-resource negative controls."""
import unittest
from resource_settle import startup, after_close


class Clock:
    def __init__(self):
        self.value = 0.0

    def now(self):
        return self.value

    def sleep(self, delay):
        # A real monotonic clock advances across calls, including at a deadline.
        self.value += max(delay, .000001)


BASE = dict(handles=100, gdi=20, user=30, private_ws=10_000_000)


class ResourceSettleTests(unittest.TestCase):
    def run_wait(self, method, sample):
        timer = Clock()
        records = []
        kwargs = dict(clock=timer.now, sleep=timer.sleep)
        if method is after_close:
            args = (lambda: sample(timer.value), BASE, records)
        else:
            args = (lambda: sample(timer.value), records)
        return timer, records, lambda: method(*args, **kwargs)

    def test_delayed_initialization_restarts_quiet_period(self):
        def sample(t):
            return dict(BASE, handles=151 if t >= 2.5 else 100)
        timer, records, run = self.run_wait(startup, sample)
        self.assertEqual(run()['handles'], 151)
        self.assertGreaterEqual(timer.value, 4.5)
        self.assertEqual(records[0]['sample']['handles'], 100)

    def test_startup_that_never_settles_fails(self):
        timer, records, run = self.run_wait(startup,
            lambda t: dict(BASE, user=30+int(t*10)))
        with self.assertRaisesRegex(AssertionError, 'Startup resource'):
            run()
        self.assertGreaterEqual(timer.value, 10)
        self.assertGreater(len(records), 100)

    def test_transient_counts_and_memory_peaks_are_retained(self):
        def sample(t):
            return dict(BASE, user=34 if t < .2 else 30,
                        private_ws=26_000_000 if t < .2 else 10_000_000)
        timer, records, run = self.run_wait(after_close, sample)
        self.assertEqual(run()['user'], 30)
        self.assertGreaterEqual(timer.value, .45)
        self.assertEqual(max(r['sample']['private_ws'] for r in records), 26_000_000)
        self.assertTrue(any(not r['within'] for r in records))

    def test_a_brief_return_does_not_hide_persistent_growth(self):
        timer, records, run = self.run_wait(after_close,
            lambda t: dict(BASE, user=30 if .2 <= t < .3 else 34))
        with self.assertRaisesRegex(AssertionError, 'Closed-tab resources'):
            run()
        self.assertGreaterEqual(timer.value, 2)

    def test_each_original_allowance_rejects_one_more(self):
        for field, value in [('handles',107), ('gdi',24), ('user',33)]:
            with self.subTest(field=field):
                _, records, run = self.run_wait(after_close,
                    lambda t: dict(BASE, **{field:value}))
                with self.assertRaises(AssertionError):
                    run()
                self.assertTrue(all(not r['within'] for r in records))

    def test_observer_overrun_cannot_be_a_late_success(self):
        timer = Clock();records = []
        def sample():
            timer.value += 3
            return dict(BASE)
        with self.assertRaises(AssertionError):
            after_close(sample, BASE, records, clock=timer.now, sleep=timer.sleep)
        self.assertEqual(len(records), 1)


if __name__ == '__main__':
    unittest.main()
