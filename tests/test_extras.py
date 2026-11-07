import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from dosyabul import clipboard_history, emoji_data, frecency, quick, scripts, sysactions, usertheme
from dosyabul.settings import AppSettings
from dosyabul.themes import THEMES
from dosyabul.websearch import clean_shortcuts, resolve_web_input


class CalculatorTests(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(quick.calculate("2*(3+4)"), "14")
        self.assertEqual(quick.calculate("10/4"), "2.5")
        self.assertEqual(quick.calculate("2^10"), "1024")
        self.assertEqual(quick.calculate("sqrt(16)+pi*0"), "4")
        self.assertEqual(quick.calculate("1,5+1"), "2.5")

    def test_rejects_unsafe(self):
        for text in ("__import__('os')", "open('x')", "1/0", "2**100000", "().__class__", "a+1"):
            with self.assertRaises(quick.CalcError):
                quick.calculate(text)

    def test_looks_like_math(self):
        self.assertTrue(quick.looks_like_math("2+2"))
        self.assertTrue(quick.looks_like_math("sqrt(9)"))
        self.assertFalse(quick.looks_like_math("chrome"))
        self.assertFalse(quick.looks_like_math("2+"))
        self.assertFalse(quick.looks_like_math("rapor 2024"))


class UnitTests(unittest.TestCase):
    def test_length_and_mass(self):
        self.assertTrue(quick.convert_units("10 km mi").startswith("6.21371"))
        self.assertTrue(quick.convert_units("1 kg to lb").startswith("2.20462"))
        self.assertEqual(quick.convert_units("1 gb mb").split()[0], "1024")

    def test_temperature(self):
        self.assertEqual(quick.convert_units("100 c f"), "212 °F")
        self.assertEqual(quick.convert_units("0 c k"), "273.15 °K")

    def test_unrelated_units_rejected(self):
        self.assertIsNone(quick.convert_units("10 km kg"))
        self.assertIsNone(quick.convert_units("merhaba dünya"))


class TimerNoteTests(unittest.TestCase):
    def test_timer(self):
        self.assertEqual(quick.parse_timer("timer 10m çay"), (600, "çay"))
        self.assertEqual(quick.parse_timer("timer 1sa30dk"), (5400, ""))
        self.assertEqual(quick.parse_timer("timer 5"), (300, ""))
        self.assertIsNone(quick.parse_timer("timer abc"))
        self.assertIsNone(quick.parse_timer("terminal"))
        self.assertTrue(quick.is_timer_prefix("timer"))

    def test_note(self):
        self.assertEqual(quick.parse_note("n: süt al"), "süt al")
        self.assertEqual(quick.parse_note("n:"), "")
        self.assertIsNone(quick.parse_note("notepad"))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "notes.txt"
            quick.append_note(path, " merhaba ", datetime(2026, 1, 2, 3, 4))
            self.assertEqual(path.read_text(encoding="utf-8"), "2026-01-02 03:04  merhaba\n")


class EmojiSystemTests(unittest.TestCase):
    def test_emoji_search_turkish(self):
        self.assertIn("🔥", [c for c, _ in emoji_data.search_emoji("ateş")])
        self.assertIn("🔥", [c for c, _ in emoji_data.search_emoji("ates")])
        self.assertTrue(emoji_data.search_emoji(""))

    def test_system_actions(self):
        self.assertEqual(sysactions.search_actions("kilit")[0].id, "lock")
        self.assertTrue(sysactions.get_action("shutdown").confirm)
        self.assertFalse(sysactions.get_action("lock").confirm)


class FrecencyTests(unittest.TestCase):
    def test_rank_and_persist(self):
        now = [1_000_000.0]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "usage.json"
            store = frecency.FrecencyStore(path, clock=lambda: now[0])
            store.record("b")
            store.record("b")
            store.record("c")
            self.assertEqual(store.rank(["a", "b", "c"], lambda item: item), ("b", "c", "a"))
            self.assertEqual(store.rank(["a", "d"], lambda item: item), ("a", "d"))
            again = frecency.FrecencyStore(path, clock=lambda: now[0])
            self.assertGreater(again.score("b"), again.score("c"))
            now[0] += 86400 * 140
            self.assertLess(again.score("b"), 0.05)


class ClipboardTests(unittest.TestCase):
    def test_history(self):
        history = clipboard_history.ClipboardHistory(limit=3)
        for text in ("bir", "iki", "üç", "dört", "iki", "   "):
            history.add(text)
        self.assertEqual(history.entries(), ("iki", "dört", "üç"))
        self.assertEqual(history.search("DORT"), ("dört",))


class ScriptTests(unittest.TestCase):
    def test_example_and_run(self):
        with tempfile.TemporaryDirectory() as folder:
            scripts.ensure_example(folder)
            found = scripts.list_scripts(folder)
            self.assertEqual([path.name for path in found], [scripts.EXAMPLE_NAME])
            if scripts.shutil.which("python") or scripts.shutil.which("py"):
                self.assertEqual(scripts.run_script(found[0]), ("Merhaba", "Dünya"))
                self.assertEqual(scripts.run_script(found[0], "x"), ())


class ThemeFileTests(unittest.TestCase):
    def test_overrides(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "theme.json"
            path.write_text('{"background": "#101010", "text": "bad", "accent": "ff0000"}', encoding="utf-8")
            overrides = usertheme.load_overrides(path)
            self.assertEqual(overrides, {"background": "#101010", "accent": "#FF0000"})
            theme = usertheme.apply_overrides(THEMES["Nord"], overrides)
            self.assertEqual(theme.background, "#101010")
            self.assertEqual(theme.text, THEMES["Nord"].text)
            self.assertEqual(usertheme.load_overrides(Path(folder) / "none.json"), {})


class WebShortcutTests(unittest.TestCase):
    def test_shortcut(self):
        shortcuts = AppSettings().web_shortcuts
        target = resolve_web_input("yt kedi videosu", shortcuts=shortcuts)
        self.assertEqual(target.url, "https://www.youtube.com/results?search_query=kedi+videosu")
        self.assertIn("google.com/search", resolve_web_input("yt").url)

    def test_clean(self):
        cleaned = clean_shortcuts({"ok": "https://x.com/?q={}", "bad": "javascript:{}", "two": "https://x/{}{}", "a b": "https://x/{}"})
        self.assertEqual(cleaned, {"ok": "https://x.com/?q={}"})
        self.assertEqual(AppSettings(web_shortcuts={"x": "ftp://a/{}"}).normalized().web_shortcuts, {})


if __name__ == "__main__":
    unittest.main()
