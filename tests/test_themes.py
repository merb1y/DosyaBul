import unittest

from dosyabul.themes import ACCENT_PRESETS, THEMES, resolve


class ResolveTests(unittest.TestCase):
    def test_known_theme(self):
        self.assertEqual(resolve("Nord").name, "Nord")

    def test_unknown_falls_back(self):
        self.assertEqual(resolve("Yok").name, "KooL Mocha")

    def test_presets_present(self):
        self.assertGreaterEqual(len(ACCENT_PRESETS), 6)
        for _name, color in ACCENT_PRESETS:
            self.assertTrue(color.startswith("#"))


class WithColorsTests(unittest.TestCase):
    def test_override_keeps_other_fields(self):
        base = THEMES["KooL Mocha"]
        themed = base.with_colors(accent="#FF0000", border="#FF0000")
        self.assertEqual(themed.accent, "#FF0000")
        self.assertEqual(themed.border, "#FF0000")
        self.assertEqual(themed.background, base.background)


if __name__ == "__main__":
    unittest.main()
