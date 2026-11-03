import json
import tempfile
import unittest
from pathlib import Path

from dosyabul.history import MAX_RECENT, LaunchHistory, LaunchRecord


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="dosyabulhist")
        self.path = Path(self._tmp.name) / "history.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_default_limit_is_five(self):
        self.assertEqual(MAX_RECENT, 5)

    def test_newest_first_and_capped(self):
        history = LaunchHistory(self.path, limit=3)
        for index in range(5):
            history.record(LaunchRecord("command", f"komut{index}", f"komut{index}"))
        self.assertEqual([entry.name for entry in history.entries()], ["komut4", "komut3", "komut2"])

    def test_same_target_moves_to_top(self):
        history = LaunchHistory(self.path)
        history.record(LaunchRecord("app:shortcut", "Ferah", r"C:\Ferah\Ferah.lnk"))
        history.record(LaunchRecord("command", "oc", "oc"))
        history.record(LaunchRecord("app:shortcut", "Ferah", r"C:\Ferah\Ferah.lnk"))
        self.assertEqual([entry.name for entry in history.entries()], ["Ferah", "oc"])

    def test_apps_and_commands_are_saved_together(self):
        history = LaunchHistory(self.path)
        history.record(LaunchRecord("app:appid", "Ferah", "Ferah.AppID", "Uygulama"))
        history.record(LaunchRecord("command", "oc", "oc", "Terminalde çalıştır"))
        reloaded = LaunchHistory(self.path)
        self.assertEqual(
            [(entry.kind, entry.name, entry.detail) for entry in reloaded.entries()],
            [("command", "oc", "Terminalde çalıştır"), ("app:appid", "Ferah", "Uygulama")],
        )

    def test_empty_target_is_ignored(self):
        history = LaunchHistory(self.path)
        history.record(LaunchRecord("command", "bos", ""))
        self.assertEqual(history.entries(), ())

    def test_corrupt_file_is_ignored(self):
        self.path.write_text("{bozuk", encoding="utf-8")
        self.assertEqual(LaunchHistory(self.path).entries(), ())

    def test_unrelated_kinds_are_ignored(self):
        self.path.write_text(
            json.dumps({"entries": [
                {"kind": "file", "name": "a.txt", "target": r"C:\a.txt"},
                {"kind": "command", "name": "oc", "target": "oc"},
            ]}),
            encoding="utf-8",
        )
        self.assertEqual([entry.name for entry in LaunchHistory(self.path).entries()], ["oc"])

    def test_clear_removes_entries(self):
        history = LaunchHistory(self.path)
        history.record(LaunchRecord("command", "oc", "oc"))
        history.clear()
        self.assertEqual(LaunchHistory(self.path).entries(), ())


if __name__ == "__main__":
    unittest.main()
