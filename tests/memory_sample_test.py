"""Working-set sampling must grow without dropping pages or hiding API errors."""
import unittest
from unittest.mock import patch

import native_test_utils as n


class WorkingSetTests(unittest.TestCase):
    def counters(self, handle, pointer, size):
        pointer._obj.private = 123456
        return 1

    def test_agent_larger_than_initial_buffer_and_growth_race(self):
        capacities = []
        def query(handle, pages, size):
            capacities.append(len(pages)-1)
            if len(capacities) < 3:
                pages[0] = 70000 if len(capacities) == 1 else 150000
                return 0
            pages[0] = 150000
            for i in range(1, 150001):
                pages[i] = 256  # shared
            pages[1] = pages[150000] = 0  # two private pages, including last
            return 1
        with patch.object(n.ps, 'QueryWorkingSet', query), \
             patch.object(n.k, 'GetLastError', return_value=24), \
             patch.object(n.ps, 'GetProcessMemoryInfo', self.counters):
            sample = n.memory_sample(123)
        self.assertGreaterEqual(capacities[-1], 150000)
        self.assertEqual(sample, dict(private_ws=2*n.mmap.PAGESIZE,
            total_ws=150000*n.mmap.PAGESIZE, private_commit=123456))

    def test_permission_error_is_not_retried_or_counted_as_zero(self):
        with patch.object(n.ps, 'QueryWorkingSet', return_value=0) as query, \
             patch.object(n.k, 'GetLastError', return_value=5):
            with self.assertRaises(OSError) as failure:
                n.memory_sample(123)
        self.assertEqual(failure.exception.winerror, 5)
        self.assertEqual(query.call_count, 1)

    def test_unbounded_required_count_does_not_allocate_it(self):
        def query(handle, pages, size):
            pages[0] = 1 << 30
            return 0
        with patch.object(n.ps, 'QueryWorkingSet', query), \
             patch.object(n.k, 'GetLastError', return_value=24):
            with self.assertRaisesRegex(RuntimeError, 'observation limit'):
                n.memory_sample(123)


if __name__ == '__main__':
    unittest.main()
