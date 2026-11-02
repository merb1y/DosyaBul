import tempfile
import unittest
from pathlib import Path

from dosyabul.settings import AppSettings, SettingsStore, clean_color


class CleanColorTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(clean_color("#ff0000"), "#FF0000")
        self.assertEqual(clean_color("ff0000"), "#FF0000")

    def test_invalid(self):
        self.assertEqual(clean_color("zzz"), "")
        self.assertEqual(clean_color(""), "")


class DefaultsTests(unittest.TestCase):
    def test_panel_defaults(self):
        s = AppSettings()
        self.assertEqual(s.panel_width, 600)
        self.assertEqual(s.visible_rows, 10)
        self.assertEqual(s.row_scale, 140)
        self.assertTrue(s.minimize_to_tray)


class NormalizeTests(unittest.TestCase):
    def test_bad_values_fall_back(self):
        s = AppSettings(accent_color="bozuk", theme="Yok", visible_rows=99, panel_width=9999).normalized()
        self.assertEqual(s.accent_color, "")
        self.assertEqual(s.theme, "KooL Mocha")
        self.assertEqual(s.visible_rows, 10)
        self.assertEqual(s.panel_width, 800)

    def test_accent_normalized(self):
        self.assertEqual(AppSettings(accent_color="00ff00").normalized().accent_color, "#00FF00")


class StoreTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            store = SettingsStore(Path(folder) / "settings.json")
            store.save(AppSettings(accent_color="#123456", minimize_to_tray=False))
            loaded = store.load()
            self.assertEqual(loaded.accent_color, "#123456")
            self.assertFalse(loaded.minimize_to_tray)


if __name__ == "__main__":
    unittest.main()
