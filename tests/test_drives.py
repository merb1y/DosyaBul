import unittest

from dosyabul.drives import discover_drives


class DiscoverDrivesTests(unittest.TestCase):
    def test_returns_tuple_of_paths(self):
        drives = discover_drives()
        self.assertIsInstance(drives, tuple)
        for drive in drives:
            self.assertEqual(len(str(drive)), 3)


if __name__ == "__main__":
    unittest.main()
