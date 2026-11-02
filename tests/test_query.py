import unittest

from dosyabul.query import QueryError, fold_text, parse_plain_query


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


if __name__ == "__main__":
    unittest.main()
