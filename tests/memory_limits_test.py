"""Check renderer-specific acceptance boundaries without launching a terminal."""
import unittest
from memory_limits import private_ws_passes, private_ws_policy


class MemoryLimitsTest(unittest.TestCase):
    def test_gdi_keeps_strict_original_budget(self):
        self.assertTrue(private_ws_passes(1, 19_999_999))
        self.assertFalse(private_ws_passes(1, 20_000_000))
        self.assertFalse(private_ws_passes(1, 22_409_216))

    def test_directx_user_approved_budget(self):
        self.assertTrue(private_ws_passes(3, 22_409_216))
        self.assertTrue(private_ws_passes(3, 25_000_000))
        self.assertFalse(private_ws_passes(3, 25_000_001))
        self.assertFalse(private_ws_passes(3, 25_210_880))

    def test_optional_opengl_has_no_numeric_gate(self):
        self.assertIsNone(private_ws_passes(2, 67_000_000))
        self.assertFalse(private_ws_policy(2)['memory_limit_required'])

    def test_invalid_observations_cannot_pass(self):
        with self.assertRaises(ValueError):
            private_ws_passes(0, 1)
        with self.assertRaises(ValueError):
            private_ws_passes(3, -1)


if __name__ == '__main__':
    unittest.main()
