"""Process ancestry must account for historical parent-PID reuse. No windows."""
import unittest
from console_process_utils import descendant_pids

class ProcessIdentityTests(unittest.TestCase):
    def test_recycled_root_pid_does_not_claim_old_services(self):
        rows = {10:(1,'terminal'), 11:(10,'host'), 12:(11,'shell'),
                20:(10,'old-service'), 21:(20,'service-child'), 30:(1,'sibling')}
        started = {10:100, 11:101, 12:102, 20:10, 21:11, 30:110}
        self.assertEqual(descendant_pids(rows, 10, started.get), {10,11,12})

    def test_recycled_intermediate_pid(self):
        rows = {10:(1,'terminal'), 11:(10,'new-host'), 12:(11,'old-orphan'),
                13:(11,'current-shell')}
        started = {10:100, 11:200, 12:150, 13:201}
        self.assertEqual(descendant_pids(rows, 10, started.get), {10,11,13})

    def test_missing_process_identity_is_not_assumed_owned(self):
        rows = {10:(1,'terminal'), 11:(10,'inaccessible'), 12:(11,'child')}
        self.assertEqual(descendant_pids(rows, 10, {10:100,12:102}.get), {10})
        self.assertEqual(descendant_pids(rows, 10, {}.get), set())
        self.assertEqual(descendant_pids({}, 10, {10:100}.get), set())

    def test_equal_clock_tick_and_unordered_rows(self):
        rows = {12:(11,'shell'), 11:(10,'host'), 10:(1,'terminal')}
        self.assertEqual(descendant_pids(rows, 10, {10:100,11:100,12:101}.get),
                         {10,11,12})

if __name__ == '__main__':
    unittest.main()
