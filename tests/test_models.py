import unittest

from dosyabul.models import FileResult, ScanReport, SearchResults


class ModelTests(unittest.TestCase):
    def test_scan_report_skipped_flag(self):
        self.assertFalse(ScanReport().skipped)
        self.assertTrue(ScanReport(errors=("hata",)).skipped)

    def test_search_results_defaults(self):
        result = SearchResults((), 0)
        self.assertEqual(result.total, 0)
        self.assertEqual(result.limit, 500)

    def test_file_result_fields(self):
        item = FileResult(id=1, name="a.txt", parent="C:\\", path="C:\\a.txt", kind="file")
        self.assertEqual(item.extension, "")


if __name__ == "__main__":
    unittest.main()
