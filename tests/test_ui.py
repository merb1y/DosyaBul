import sys
sys.path.insert(0, r'C:\Users\merby\OC\DosyaBul')
import tempfile, threading, tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from dosyabul.actions import configure_windows
from dosyabul.app import FinderApp, format_count
from dosyabul.database import IndexDatabase
from dosyabul.indexer import Indexer


class UiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='dosyabului')
        base = Path(self._tmp.name)
        self.folder = base / 'C'
        self.folder.mkdir()
        (self.folder / 'Is Plani.txt').write_text('x', encoding='utf-8')
        self.db = IndexDatabase(base / 'v' / 'index.sqlite3')
        root = self.db.add_root(self.folder)
        Indexer(self.db).scan((root,), threading.Event())
        try:
            configure_windows()
            self.window = tk.Tk()
        except tk.TclError as error:
            self._tmp.cleanup()
            self.skipTest(f'Grafik oturumu yok: {error}')
        self.window.withdraw()
        self.app = FinderApp(self.window, self.db, drive_provider=Mock(return_value=(self.folder,)), auto_start=False, start_hidden=True, enable_hotkey=False, enable_tray=False)
        self.app._cancel_timer('_event_after')

    def tearDown(self):
        self.app.quit_app()
        self.app.wait_for_background(timeout=5)
        self.db.close()
        self._tmp.cleanup()

    def test_count_format(self):
        self.assertEqual(format_count(1234567), '1.234.567')

    def test_single_search_input(self):
        def walk(p):
            for c in p.winfo_children():
                yield c
                yield from walk(c)
        entries = [w for w in walk(self.window) if isinstance(w, tk.Entry)]
        self.assertEqual(len(entries), 1)

    def test_file_search_and_open(self):
        self.app.render_results(self.db.search(('is', 'plani')))
        self.assertEqual(self.app._selected_item().name, 'Is Plani.txt')
        with patch('dosyabul.app.actions.open_item') as opener:
            self.app.open_selected()
        opener.assert_called_once()

    def test_blank_query_does_not_search(self):
        with patch.object(self.db, 'search') as search:
            self.app.query_var.set('')
            self.app._begin_search()
        search.assert_not_called()

    def test_toggle_popup(self):
        self.assertFalse(self.app.visible)
        self.app.events.put(('toggle',))
        self.app._drain_events()
        self.assertTrue(self.app.visible)

    def test_accent_updates_search_box(self):
        self.app.settings.accent_color = '#FF0000'
        self.app._apply_settings()
        self.assertEqual(self.app.search_box['bg'], '#FF0000')


if __name__ == '__main__':
    unittest.main()
