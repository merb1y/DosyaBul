import tempfile
import threading
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from dosyabul.actions import configure_windows
from dosyabul.app import MODE_ALL, MODE_APPS, MODE_CLIPBOARD, MODE_EMOJI, MODE_SCRIPTS, MODE_SYSTEM, FinderApp
from dosyabul.database import IndexDatabase


class ExtraUiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="dosyabulextra")
        base = Path(self._tmp.name)
        self.db = IndexDatabase(base / "v" / "index.sqlite3")
        try:
            configure_windows()
            self.window = tk.Tk()
        except tk.TclError as error:
            self._tmp.cleanup()
            self.skipTest(f"Grafik oturumu yok: {error}")
        self.window.withdraw()
        self.app = FinderApp(self.window, self.db, drive_provider=Mock(return_value=()), auto_start=False,
                             start_hidden=True, enable_hotkey=False, enable_tray=False)
        self.app._cancel_timer("_event_after")

    def tearDown(self):
        self.app.quit_app()
        self.app.wait_for_background(timeout=5)
        self.db.close()
        self._tmp.cleanup()

    def search(self, text, mode=MODE_ALL):
        self.app.set_mode(mode, schedule=False)
        self.app.query_var.set(text)
        self.app._begin_search()
        return [(item.kind, item.name, item.target) for item in self.app.items.values()]

    def test_calculator_prefix_and_auto(self):
        self.assertEqual(self.search("= 2*(3+4)")[0][0:3:2], ("copy", "14"))
        self.assertEqual(self.search("2+2", MODE_APPS)[0][2], "4")

    def test_unit_conversion(self):
        self.assertEqual(self.search("100 c f", MODE_APPS)[0][2], "212 °F")

    def test_note_and_timer_items(self):
        self.assertEqual(self.search("n: süt al")[0][0], "note")
        self.assertEqual(self.search("timer 10m çay")[0][2], "600|çay")
        self.assertEqual(self.search("n:")[0][0], "notefile")

    def test_note_is_saved(self):
        self.search("n: deneme")
        self.app.open_selected()
        self.assertIn("deneme", self.app.notes_path.read_text(encoding="utf-8"))

    def test_emoji_prefix_and_mode(self):
        self.assertTrue(any(kind == "emoji" for kind, _, _ in self.search(":ateş")))
        self.assertTrue(self.search("", MODE_EMOJI))

    def test_system_mode_and_command(self):
        self.assertEqual(self.search("kilit", MODE_SYSTEM)[0][2], "lock")
        self.assertTrue(any(target == "shutdown" for _, _, target in self.search("-p kapat")))

    def test_clipboard_mode(self):
        self.app.clipboard.add("kopya metin")
        self.assertEqual(self.search("", MODE_CLIPBOARD)[0][2], "kopya metin")
        self.assertEqual(self.search("-c metin")[0][0], "clip")

    def test_system_action_needs_confirmation(self):
        self.search("kapat", MODE_SYSTEM)
        self.app.tree.selection_set("system:shutdown")
        with patch("dosyabul.app.messagebox.askyesno", return_value=False) as ask, \
                patch("dosyabul.app.sysactions.run_action") as run:
            self.app.open_selected()
        ask.assert_called_once()
        run.assert_not_called()

    def test_scripts_mode_lists_example(self):
        rows = self.search("", MODE_SCRIPTS)
        self.assertEqual(rows[0][0], "script")

    def test_web_shortcut_in_search(self):
        row = self.search("!yt kedi")[0]
        self.assertIn("youtube.com/results?search_query=kedi", row[2])

    def test_frecency_promotes_used_app(self):
        from dosyabul.applications import ResultItem
        first = ResultItem("a", "Alfa", "", "app:shortcut", "C:/a.lnk")
        second = ResultItem("b", "Beta", "", "app:shortcut", "C:/b.lnk")
        self.app._record_usage(second)
        self.assertEqual(self.app._rank_items([first, second])[0].name, "Beta")

    def test_cycle_includes_new_modes(self):
        self.app.set_mode(MODE_ALL, schedule=False)
        seen = set()
        for _ in range(12):
            self.app.cycle_mode()
            seen.add(self.app._mode)
        self.assertTrue({MODE_CLIPBOARD, MODE_EMOJI, MODE_SYSTEM, MODE_SCRIPTS} <= seen)



    def test_ssh_and_process_modes_render(self):
        rows_ssh = self.search("ssh user@example.com")
        self.assertEqual(rows_ssh[0][0], "ssh")
        rows_proc = self.search("-k python")
        self.assertTrue(all(kind == "process" for kind, _, _ in rows_proc))


    def test_pinned_apps_limit_and_order(self):
        for i in range(10):
            self.app.pins.pin(f"C:/Apps/App{i}.exe", name=f"App {i}")
        rows = self.search("")
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0][1], "App 9")
        self.assertEqual(rows[7][1], "App 2")
        self.app.pins.unpin("C:/Apps/App9.exe")
        rows_after = self.search("")
        self.assertEqual(rows_after[0][1], "App 8")

if __name__ == "__main__":
    unittest.main()
