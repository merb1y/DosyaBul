import tempfile
import unittest
from pathlib import Path

from dosyabul.instance import InstanceGuard


class InstanceGuardTests(unittest.TestCase):
    def test_acquires_and_blocks_second(self):
        with tempfile.TemporaryDirectory(prefix="dosyabulinst") as folder:
            first = InstanceGuard(Path(folder))
            self.assertTrue(first.acquired)
            second = InstanceGuard(Path(folder))
            self.assertFalse(second.acquired)
            first.close()
            second.close()

    def test_signal_existing_is_safe(self):
        with tempfile.TemporaryDirectory(prefix="dosyabulinst") as folder:
            guard = InstanceGuard(Path(folder))
            guard.signal_existing()
            guard.close()


if __name__ == "__main__":
    unittest.main()
