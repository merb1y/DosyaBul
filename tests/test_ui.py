import sys
sys.path.insert(0, r'C:\Users\merby\OC\DosyaBul')
import tempfile, threading, time, tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from dosyabul.actions import configure_windows
from dosyabul.app import FinderApp, format_count
from dosyabul.applications import LauncherResults, ResultItem
from dosyabul.database import IndexDatabase
from dosyabul.history import LaunchRecord
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

    def test_home_mode_searches_apps_only(self):
        self.assertEqual(self.app._mode, 'Uygulamalar')

    def test_cycle_mode_backwards(self):
        self.app.set_mode('Uygulamalar')
        self.app.cycle_mode(step=-1)
        self.assertEqual(self.app._mode, 'Tümü')

    def test_mode_switch_shortcuts_are_bound(self):
        self.assertTrue(self.app.root.bind('<Control-Tab>'))
        self.assertTrue(self.app.root.bind('<Control-Shift-Tab>'))
        self.assertTrue(self.app.search_entry.bind('<Tab>'))
        self.assertTrue(self.app.search_entry.bind('<Shift-Tab>'))

    def test_popup_refreshes_stale_app_list(self):
        self.app.auto_start = True
        self.app._apps_refreshed_at = 0.0
        with patch.object(self.app, '_start_application_refresh') as starter:
            self.app.show_popup()
        starter.assert_called_once()

    def test_popup_skips_fresh_app_list(self):
        self.app.auto_start = True
        self.app._apps_refreshed_at = time.monotonic()
        with patch.object(self.app, '_start_application_refresh') as starter:
            self.app.show_popup()
        starter.assert_not_called()

    def test_empty_query_shows_recent_apps_and_commands(self):
        self.app.history.record(LaunchRecord('app:shortcut', 'Ferah', r'C:\Program Files\Ferah\Ferah.lnk', 'Uygulama'))
        self.app.history.record(LaunchRecord('command', 'oc', 'oc', 'Terminalde çalıştır'))
        self.app.set_mode('Tümü')
        self.app._begin_search()
        names = [self.app.tree.item(item, 'text') for item in self.app.tree.get_children()]
        self.assertEqual(names, ['oc', 'Ferah'])
        self.assertIn('Son kullanılanlar', self.app.placeholder['text'])

    def test_home_mode_lists_only_recent_apps(self):
        self.app.history.record(LaunchRecord('app:shortcut', 'Ferah', r'C:\Program Files\Ferah\Ferah.lnk', 'Uygulama'))
        self.app.history.record(LaunchRecord('command', 'oc', 'oc', 'Terminalde çalıştır'))
        self.app._begin_search()
        names = [self.app.tree.item(item, 'text') for item in self.app.tree.get_children()]
        self.assertEqual(names, ['Ferah'])

    def test_empty_query_without_history_keeps_empty_panel(self):
        self.app._begin_search()
        self.assertEqual(self.app.tree.get_children(), ())

    def test_opening_app_records_recent(self):
        item = ResultItem('x', 'Ferah', 'Uygulama', 'app:shortcut', r'C:\Program Files\Ferah\Ferah.lnk')
        self.app.render_results(LauncherResults((item,), 1))
        with patch('dosyabul.app.launch_application') as launcher:
            self.app.open_selected()
        launcher.assert_called_once()
        entries = self.app.history.entries()
        self.assertEqual([(entry.kind, entry.name) for entry in entries], [('app:shortcut', 'Ferah')])

    def test_opening_command_records_recent(self):
        item = ResultItem('command', 'oc', 'Terminalde çalıştır', 'command', 'oc')
        self.app.render_results(LauncherResults((item,), 1))
        with patch('dosyabul.app.launch_terminal_command') as launcher:
            self.app.open_selected()
        launcher.assert_called_once()
        entries = self.app.history.entries()
        self.assertEqual([(entry.kind, entry.target) for entry in entries], [('command', 'oc')])

    def test_home_mode_builds_command_for_slash_query(self):
        self.assertEqual(self.app._mode, 'Uygulamalar')
        self.app.settings.search_commands = True
        self.app.query_var.set('/git status')
        self.app._begin_search()
        item = self.app._selected_item()
        self.assertIsNotNone(item)
        self.assertEqual(item.kind, 'command')
        self.assertEqual(item.target, 'git status')

    def test_home_mode_searches_apps_without_slash(self):
        self.assertEqual(self.app._mode, 'Uygulamalar')
        self.app.query_var.set('uygulama')
        with patch.object(self.app, '_search_apps', return_value=()) as searcher:
            self.app._begin_search()
        searcher.assert_called_once()


if __name__ == '__main__':
    unittest.main()
