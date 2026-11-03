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
        self.assertEqual(s.default_mode, "Uygulamalar")


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

    def test_old_default_mode_migrates_to_apps(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text('{"default_mode": "Tümü"}', encoding="utf-8")
            self.assertEqual(SettingsStore(path).load().default_mode, "Uygulamalar")

    def test_explicit_all_mode_is_kept_after_migration(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text('{"default_mode": "Tümü", "settings_version": 2}', encoding="utf-8")
            self.assertEqual(SettingsStore(path).load().default_mode, "Tümü")


if __name__ == "__main__":
    unittest.main()
