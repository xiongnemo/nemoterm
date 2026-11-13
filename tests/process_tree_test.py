"""Process ancestry must account for historical parent-PID reuse. No windows."""
import unittest
from unittest.mock import patch
from console_process_utils import descendant_pids, workload_process_role
import console_process_utils as process_utils

class ProcessIdentityTests(unittest.TestCase):
    def test_two_tab_single_image_and_sidecar_host_roles(self):
        frontend = r'D:\app\dist\nemoterm.exe'
        for host in (frontend, r'd:/APP/dist/OpenConsole.EXE'):
            processes = [dict(pid=10, parent=1, path=frontend),
                         dict(pid=11, parent=10, path=host),
                         dict(pid=12, parent=10, path=r'C:\Python\python.exe'),
                         dict(pid=13, parent=10, path=host),
                         dict(pid=14, parent=10, path=r'C:\Python\python.exe')]
            self.assertEqual([workload_process_role(p, 10, frontend) for p in processes],
                             ['frontend', 'hosts', 'clients', 'hosts', 'clients'])

    def test_host_role_needs_exact_path_and_direct_parent(self):
        frontend = r'D:\app\dist\nemoterm.exe'
        for parent, path in [(10, r'C:\unrelated\OpenConsole.exe'),
                             (10, r'D:\app\dist\other\nemoterm.exe'),
                             (12, r'D:\app\dist\OpenConsole.exe'),
                             (12, frontend)]:
            self.assertEqual(workload_process_role(
                dict(pid=20, parent=parent, path=path), 10, frontend), 'clients')

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

    def test_memory_read_failure_of_signaled_process_is_recorded(self):
        exited=[]
        def status(handle,pointer):
            pointer._obj.value=0
            return 1
        with patch.object(process_utils,'memory_sample',side_effect=PermissionError('closed')), \
             patch.object(process_utils.k,'WaitForSingleObject',return_value=0), \
             patch.object(process_utils.k,'GetExitCodeProcess',status):
            self.assertIsNone(process_utils.sample_process_memory(123,45,exited))
        self.assertEqual(exited[0]['pid'],45)
        self.assertTrue(exited[0]['signaled'])
        self.assertEqual(exited[0]['exit_code'],0)

    def test_live_or_unverifiable_process_read_failure_still_fails(self):
        for result in (258,0xffffffff):  # WAIT_TIMEOUT, WAIT_FAILED
            exited=[]
            with patch.object(process_utils,'memory_sample',side_effect=PermissionError('denied')), \
                 patch.object(process_utils.k,'WaitForSingleObject',return_value=result):
                with self.assertRaises(PermissionError):
                    process_utils.sample_process_memory(123,45,exited)
            self.assertEqual(exited,[])

if __name__ == '__main__':
    unittest.main()
