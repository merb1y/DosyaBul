import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dosyabul.applications import (
    Application, ApplicationIndex, ResultItem, builtin_applications, _key,
)


class KeyTests(unittest.TestCase):
    def test_key_returns_string(self):
        key = _key("exe", "notepad.exe")
        self.assertIsInstance(key, str)
        self.assertTrue(key)

    def test_key_differs_by_kind(self):
        self.assertNotEqual(_key("exe", "a"), _key("uri", "a"))


class SearchKeyTests(unittest.TestCase):
    def test_search_key_contains_name_and_keywords(self):
        app = Application("k", "WezTerm", r"C:\WezTerm\wezterm-gui.exe", "exe", keywords="terminal konsol")
        self.assertIn("wezterm", app.search_key)
        self.assertIn("terminal", app.search_key)


class IndexTests(unittest.TestCase):
    def test_search_matches_by_name(self):
        index = ApplicationIndex()
        with index._lock:
            index._applications = (
                Application("k1", "Notepad", "notepad.exe", "exe", keywords="metin editor"),
                Application("k2", "Hesap Makinesi", "calculator:", "uri"),
            )
        results = index.search("notepad")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Notepad")

    def test_search_matches_keywords(self):
        index = ApplicationIndex()
        with index._lock:
            index._applications = (Application("k", "X", "x.exe", "exe", keywords="terminal konsol"),)
        self.assertEqual(len(index.search("terminal")), 1)

    def test_blank_search_is_empty(self):
        index = ApplicationIndex()
        self.assertEqual(index.search("  "), ())


class RefreshTests(unittest.TestCase):
    def test_installed_shortcut_shadows_builtin_with_same_name(self):
        index = ApplicationIndex()
        with tempfile.TemporaryDirectory(prefix="dosyabulapp") as folder:
            (Path(folder) / "Notepad.lnk").write_bytes(b"")
            builtin = (Application("b", "Notepad", "notepad.exe", "exe", priority=100),)
            with patch("dosyabul.applications.builtin_applications", return_value=builtin):
                index.refresh(directories=(Path(folder),), include_start_apps=False)
        apps = index.all()
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0].launch_kind, "shortcut")

    def test_duplicate_name_keeps_best_priority(self):
        index = ApplicationIndex()
        with tempfile.TemporaryDirectory(prefix="dosyabulapp") as folder:
            (Path(folder) / "WezTerm.lnk").write_bytes(b"")
            builtin = (Application("b", "WezTerm", "wezterm-gui.exe", "exe", priority=0),)
            with patch("dosyabul.applications.builtin_applications", return_value=builtin):
                index.refresh(directories=(Path(folder),), include_start_apps=False)
        apps = index.all()
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0].launch_kind, "shortcut")
        self.assertEqual(apps[0].priority, 0)


class ResultItemTests(unittest.TestCase):
    def test_path_property(self):
        item = ResultItem("k", "Ad", "detay", "file", r"C:\a\b.txt")
        self.assertEqual(item.path, r"C:\a\b.txt")


if __name__ == "__main__":
    unittest.main()
