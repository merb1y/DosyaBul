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
        self.assertEqual(names, ['/oc', 'Ferah'])
        self.assertIn('Son kullanılanlar', self.app.placeholder['text'])

    def test_home_mode_lists_recent_apps_and_commands(self):
        self.app.history.record(LaunchRecord('app:shortcut', 'Ferah', r'C:\Program Files\Ferah\Ferah.lnk', 'Uygulama'))
        self.app.history.record(LaunchRecord('command', 'oc', 'oc', 'Terminalde çalıştır'))
        self.app._begin_search()
        names = [self.app.tree.item(item, 'text') for item in self.app.tree.get_children()]
        self.assertEqual(names, ['/oc', 'Ferah'])
        # Komut satırı seçilip Enter'a basılınca terminalde çalışır.
        command_item = self.app._selected_item()
        self.assertEqual(command_item.kind, 'command')
        self.assertEqual(command_item.target, 'oc')
        with patch('dosyabul.app.launch_terminal_command') as launcher:
            self.app.open_selected()
        launcher.assert_called_once()

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

    def test_dash_s_shows_settings_result(self):
        self.app.query_var.set('-s')
        self.app._begin_search()
        item = self.app._selected_item()
        self.assertIsNotNone(item)
        self.assertEqual(item.kind, 'settings')
        self.assertEqual(item.name, 'DosyaBul Ayarları')
        with patch.object(self.app, 'open_settings') as opener:
            self.app.open_selected()
        opener.assert_called_once()

    def test_dash_r_lists_installed_programs_and_uninstalls(self):
        from dosyabul.uninstall import InstalledProgram
        with patch('dosyabul.app.search_installed_programs') as searcher:
            searcher.return_value = (InstalledProgram('1', 'Stremio', '5.0', 'Stremio', r'"C:\x\unins000.exe"'),)
            self.app.query_var.set('-r stremio')
            self.app._begin_search()
            self.app._search_future.result(timeout=5)
            self.app._drain_events()
            self.app._cancel_timer('_event_after')
            searcher.assert_called_once_with('stremio')
        item = self.app._selected_item()
        self.assertIsNotNone(item)
        self.assertEqual(item.kind, 'uninstall')
        self.assertEqual(item.name, 'Stremio')
        with patch('dosyabul.app.messagebox.askyesno', return_value=True), \
             patch('dosyabul.app.launch_uninstall') as uninstaller:
            self.app.open_selected()
        uninstaller.assert_called_once_with(r'"C:\x\unins000.exe"')

    def test_dash_r_declined_uninstall_does_nothing(self):
        from dosyabul.uninstall import InstalledProgram
        with patch('dosyabul.app.search_installed_programs') as searcher:
            searcher.return_value = (InstalledProgram('1', 'Stremio', '5.0', 'Stremio', r'"C:\x\unins000.exe"'),)
            self.app.query_var.set('-r stremio')
            self.app._begin_search()
            self.app._search_future.result(timeout=5)
            self.app._drain_events()
            self.app._cancel_timer('_event_after')
        with patch('dosyabul.app.messagebox.askyesno', return_value=False), \
             patch('dosyabul.app.launch_uninstall') as uninstaller:
            self.app.open_selected()
        uninstaller.assert_not_called()

    def test_dash_h_lists_help_rows(self):
        self.app.query_var.set('-h')
        self.app._begin_search()
        items = list(self.app.items.values())
        kinds = {item.kind for item in items}
        self.assertEqual(kinds, {'help'})
        names = ' '.join(item.name for item in items)
        for expected in ('-s', '-r program', '/komut', '!arama', '-y', '-q', 'Tab / Ctrl+Tab', 'Alt + F2'):
            self.assertIn(expected, names)
        # Komut satırı Enter ile denenir: sorgu doldurulur, kısayol satırı pas geçer.
        rendered = list(self.app.items.values())
        self.assertTrue(rendered)
        row = next(item for item in rendered if item.target == '-s')
        self.app.tree.selection_set(row.key)
        self.app.query_var.set('')
        self.app.open_selected()
        self.assertEqual(self.app.query_var.get(), '-s')
        self.app.query_var.set('-h')
        self.app._begin_search()
        rendered = list(self.app.items.values())
        shortcut = next((item for item in rendered if item.target == ''), None)
        if shortcut is not None:
            self.app.tree.selection_set(shortcut.key)
            self.app.query_var.set('')
            self.app.open_selected()
            self.assertEqual(self.app.query_var.get(), '')

    def test_dash_y_refreshes(self):
        self.app.query_var.set('-y')
        self.app._begin_search()
        item = self.app._selected_item()
        self.assertEqual(item.kind, 'refresh')
        with patch.object(self.app, 'refresh_all') as refresher:
            self.app.open_selected()
        refresher.assert_called_once()

    def test_dash_q_confirmed_quits(self):
        self.app.query_var.set('-q')
        self.app._begin_search()
        item = self.app._selected_item()
        self.assertEqual(item.kind, 'quit')
        with patch('dosyabul.app.messagebox.askyesno', return_value=True), \
             patch.object(self.app, 'quit_app') as quitter:
            self.app.open_selected()
        quitter.assert_called_once()
        with patch('dosyabul.app.messagebox.askyesno', return_value=False), \
             patch.object(self.app, 'quit_app') as quitter:
            self.app.open_selected()
        quitter.assert_not_called()


if __name__ == '__main__':
    unittest.main()
