import io
import unittest

from dosyabul.websearch import SEARCH_ENGINES, build_search_url, resolve_web_input


class ResolveWebInputTests(unittest.TestCase):
    def test_search_phrase(self):
        target = resolve_web_input("merhaba dunya", "Google")
        self.assertIn("google.com/search", target.url)
        self.assertEqual(target.detail, "Web'de ara")

    def test_full_url_is_opened(self):
        target = resolve_web_input("https://example.com/yol", "Google")
        self.assertEqual(target.url, "https://example.com/yol")
        self.assertEqual(target.detail, "Adresi ac")

    def test_bare_domain_gets_scheme(self):
        target = resolve_web_input("youtube.com", "Google")
        self.assertEqual(target.url, "https://youtube.com")

    def test_blank_raises(self):
        with self.assertRaises(ValueError):
            resolve_web_input("  ")

    def test_engines_available(self):
        self.assertTrue(set(SEARCH_ENGINES) >= {"Google", "DuckDuckGo", "Bing"})

    def test_engine_choice_changes_url(self):
        self.assertIn("duckduckgo.com", build_search_url("kedi", "DuckDuckGo"))


if __name__ == "__main__":
    unittest.main()
