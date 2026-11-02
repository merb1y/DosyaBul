import unittest

from dosyabul import startup


class StartupTests(unittest.TestCase):
    def test_api_present(self):
        self.assertTrue(callable(startup.is_startup_enabled))
        self.assertTrue(callable(startup.set_startup))

    def test_is_startup_returns_bool(self):
        self.assertIsInstance(startup.is_startup_enabled(), bool)


if __name__ == "__main__":
    unittest.main()
