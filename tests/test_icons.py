import os
import unittest

from dosyabul import icons


@unittest.skipUnless(os.name == 'nt', 'Windows gerektirir')
class IconTests(unittest.TestCase):
    def test_loads_icon_from_exe(self):
        data = icons.load_icon(r'C:\Windows\System32\notepad.exe')
        self.assertIsNotNone(data)
        width, height, rgba = data
        self.assertGreater(width, 0)
        self.assertEqual(len(rgba), width * height * 4)

    def test_empty_path_returns_none(self):
        self.assertIsNone(icons.load_icon(''))

    def test_shortcut_loads_without_overlay_arrow(self):
        directory = os.environ.get('APPDATA')
        if not directory:
            self.skipTest('APPDATA yok')
        shortcut = os.path.join(directory, 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'File Explorer.lnk')
        if not os.path.isfile(shortcut):
            self.skipTest('Kisayol bulunamadi')
        self.assertTrue(icons._is_shortcut(shortcut))
        data = icons.load_icon(shortcut)
        self.assertIsNotNone(data)
        width, height, rgba = data
        self.assertEqual(len(rgba), width * height * 4)


if __name__ == '__main__':
    unittest.main()
