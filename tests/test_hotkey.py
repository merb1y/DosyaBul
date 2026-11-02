import unittest

from dosyabul.hotkey import (
    DEFAULT_SPEC, MOD_ALT, MOD_CONTROL, HotkeySpec,
    captured_hotkey, format_hotkey, parse_hotkey, parse_key,
)


class ParseHotkeyTests(unittest.TestCase):
    def test_parse_modifiers_and_key(self):
        spec = parse_hotkey("Ctrl + F3")
        self.assertEqual(spec.modifiers, MOD_CONTROL)
        self.assertEqual(format_hotkey(spec), "Ctrl + F3")

    def test_default_when_blank(self):
        self.assertEqual(parse_hotkey(""), DEFAULT_SPEC)

    def test_missing_key_raises(self):
        with self.assertRaises(ValueError):
            parse_hotkey("Ctrl")

    def test_requires_modifier(self):
        with self.assertRaises(ValueError):
            HotkeySpec(0, 0x71).normalized()


class ParseKeyTests(unittest.TestCase):
    def test_named_key(self):
        self.assertEqual(parse_key("space"), 0x20)

    def test_letter(self):
        self.assertEqual(parse_key("a"), ord("A"))

    def test_function_key(self):
        self.assertEqual(parse_key("F3"), 0x72)


class FormatTests(unittest.TestCase):
    def test_format_order(self):
        self.assertEqual(format_hotkey(HotkeySpec(MOD_CONTROL | MOD_ALT, 0x20)), "Ctrl + Alt + Space")


if __name__ == "__main__":
    unittest.main()
