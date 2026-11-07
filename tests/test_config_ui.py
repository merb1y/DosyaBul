import tempfile, tkinter as tk, unittest
from pathlib import Path
from unittest.mock import Mock
from dosyabul import app as appmod
from dosyabul.app import FinderApp
from dosyabul.database import IndexDatabase

class ConfigUiTests(unittest.TestCase):
    def test_entries_modes_and_font(self):
        tmp = tempfile.TemporaryDirectory()
        base = Path(tmp.name)
        (base / "theme.json").write_text('{"font":"Consolas","modes":["Uygulamalar","Emoji"],"mode_chip":false,"placeholder":"Hey","entries":[{"name":"Benim Site","url":"https://example.com","keywords":"blog"}]}', encoding="utf-8")
        db = IndexDatabase(base / "index.sqlite3")
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("Grafik oturumu yok")
        root.withdraw()
        app = FinderApp(root, db, drive_provider=Mock(return_value=()), auto_start=False, start_hidden=True, enable_hotkey=False, enable_tray=False)
        try:
            self.assertEqual(appmod.FONT_FAMILY, "Consolas")
            app.set_mode("Uygulamalar", schedule=False)
            app.cycle_mode()
            self.assertEqual(app._mode, "Emoji")
            app.cycle_mode()
            self.assertEqual(app._mode, "Uygulamalar")
            app.query_var.set("blog")
            app._begin_search()
            self.assertEqual([i.kind for i in app.items.values()][0], "custom:url")
            self.assertEqual(app._placeholder_text(), "Hey")
            app.events.put(("tray_settings",))
            app._drain_events()
            self.assertIsNotNone(app._settings_window)
            self.assertEqual(app._settings_window.state(), "normal")
            self.assertEqual(app._settings_window.transient(), "")
        finally:
            app.quit_app(); app.wait_for_background(timeout=5); db.close(); tmp.cleanup()
            appmod.FONT_FAMILY = "Cascadia Code"

if __name__ == "__main__":
    unittest.main()
