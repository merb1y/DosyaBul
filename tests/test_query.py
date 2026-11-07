import tempfile
import unittest
from pathlib import Path

from dosyabul.dmenu import filter_dmenu_lines
from dosyabul.query import QueryError, fold_text, fuzzy_score, parse_plain_query
from dosyabul.rofi_modes import parse_ssh_config


class FoldTextTests(unittest.TestCase):
    def test_turkish_letters_are_folded(self):
        self.assertEqual(fold_text("İŞ ÇÖĞÜ"), "is cogu")
        self.assertEqual(fold_text("ışçöğü"), "iscogu")

    def test_empty_input(self):
        self.assertEqual(fold_text(""), "")
        self.assertEqual(fold_text(None), "")


class ParseQueryTests(unittest.TestCase):
    def test_plain_words(self):
        self.assertEqual(parse_plain_query("is plani"), ("is", "plani"))

    def test_quoted_phrase(self):
        self.assertEqual(parse_plain_query('"is plani"'), ("is plani",))

    def test_blank(self):
        self.assertEqual(parse_plain_query("   "), ())

    def test_unclosed_quote_raises(self):
        with self.assertRaises(QueryError):
            parse_plain_query('"acik tirnak')


class FuzzyScoreTests(unittest.TestCase):
    def test_subsequence_word_boundaries(self):
        score_vsc = fuzzy_score("vsc", "Visual Studio Code")
        self.assertIsNotNone(score_vsc)
        self.assertGreater(score_vsc, 300)
        self.assertIsNone(fuzzy_score("xyz", "Visual Studio Code"))

    def test_dmenu_filter(self):
        filtered = filter_dmenu_lines(["Firefox", "Visual Studio Code", "WezTerm"], "vsc")
        self.assertEqual(filtered[0][1], "Visual Studio Code")

    def test_ssh_config_parser(self):
        with tempfile.TemporaryDirectory() as tmp:
            ssh_dir = Path(tmp)
            (ssh_dir / "config").write_text(
                "Host prod-db\n  HostName 10.0.0.5\n  User admin\n  Port 2222\nHost *\n  User root\n",
                encoding="utf-8",
            )
            hosts = parse_ssh_config(ssh_dir)
            self.assertEqual(len(hosts), 1)
            self.assertEqual(hosts[0].alias, "prod-db")
            self.assertIn("admin@10.0.0.5", hosts[0].detail)


if __name__ == "__main__":
    unittest.main()
