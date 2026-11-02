import os
import time
import unittest

from dosyabul import tray


@unittest.skipUnless(os.name == 'nt', 'Windows gerektirir')
class TrayTests(unittest.TestCase):
    def test_install_and_stop(self):
        icon = tray.TrayIcon(tooltip='DosyaBul Test')
        self.assertTrue(icon.start())
        self.assertTrue(icon.available)
        icon.stop()


if __name__ == '__main__':
    unittest.main()
