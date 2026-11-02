import tempfile
import threading
import unittest
from pathlib import Path

from dosyabul.database import IndexDatabase
from dosyabul.indexer import Indexer


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="dosyabuldb")
        base = Path(self._tmp.name)
        self.folder = base / "C"
        self.folder.mkdir()
        (self.folder / "Is Plani.txt").write_text("x", encoding="utf-8")
        (self.folder / "Belgeler").mkdir()
        (self.folder / "Belgeler" / "not.txt").write_text("not", encoding="utf-8")
        self.db = IndexDatabase(base / "v" / "index.sqlite3")
        self.root = self.db.add_root(self.folder)
        Indexer(self.db).scan((self.root,), threading.Event())

    def tearDown(self):
        self.db.close()
        self._tmp.cleanup()

    def test_roots_listed(self):
        self.assertEqual(len(self.db.list_roots()), 1)

    def test_search_file(self):
        result = self.db.search(("is", "plani"))
        self.assertEqual(result.total, 1)
        self.assertEqual(result.files[0].name, "Is Plani.txt")

    def test_search_directory_kind(self):
        result = self.db.search(("belgeler",))
        self.assertTrue(any(f.kind == "directory" for f in result.files))

    def test_blank_search(self):
        self.assertEqual(self.db.search(()).total, 0)

    def test_overview_counts(self):
        roots, items, _last = self.db.overview()
        self.assertEqual(roots, 1)
        self.assertGreaterEqual(items, 3)


if __name__ == "__main__":
    unittest.main()
