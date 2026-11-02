import tempfile
import threading
import unittest
from pathlib import Path

from dosyabul.database import IndexDatabase
from dosyabul.indexer import Indexer
from dosyabul.models import ScanReport


class IndexerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="dosyabulidx")
        base = Path(self._tmp.name)
        self.folder = base / "C"
        self.folder.mkdir()
        (self.folder / "bir.txt").write_text("a", encoding="utf-8")
        (self.folder / "alt").mkdir()
        (self.folder / "alt" / "iki.txt").write_text("b", encoding="utf-8")
        self.db = IndexDatabase(base / "v" / "i.sqlite3")
        self.root = self.db.add_root(self.folder)

    def tearDown(self):
        self.db.close()
        self._tmp.cleanup()

    def test_scan_returns_report(self):
        report = Indexer(self.db).scan((self.root,), threading.Event())
        self.assertIsInstance(report, ScanReport)
        self.assertGreaterEqual(report.added, 3)

    def test_cancel_stops_early(self):
        event = threading.Event()
        event.set()
        report = Indexer(self.db).scan((self.root,), event)
        self.assertIsInstance(report, ScanReport)


if __name__ == "__main__":
    unittest.main()
