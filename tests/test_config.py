import tempfile, unittest
from pathlib import Path
from dosyabul import usertheme

class ConfigTests(unittest.TestCase):
    def test_full_config(self):
        with tempfile.TemporaryDirectory() as f:
            p = Path(f) / "theme.json"
            p.write_text("""{"extends":"Nord","font":"Consolas","border_width":99,"header_height":"x","placeholder":"Ne ararsın?",
              "mode_chip":false,"modes":["Web","Web","Yok","Emoji"],
              "entries":[{"name":"GH","url":"https://github.com"},{"name":"Çift","url":"a","run":"b"},{"url":"x"},{"name":"T","terminal":"dir","keywords":"k"}]}""", encoding="utf-8")
            c = usertheme.load_config(p)
            self.assertEqual((c["extends"], c["font"], c["border_width"], c["placeholder"], c["mode_chip"]), ("Nord", "Consolas", 8, "Ne ararsın?", False))
            self.assertNotIn("header_height", c)
            self.assertEqual(c["modes"], ["Web", "Emoji"])
            self.assertEqual([(e["name"], e["action"]) for e in c["entries"]], [("GH", "url"), ("T", "terminal")])

    def test_missing_or_broken(self):
        with tempfile.TemporaryDirectory() as f:
            self.assertEqual(usertheme.load_config(Path(f) / "x.json"), {"colors": {}, "entries": []})
            p = usertheme.ensure_example(Path(f) / "theme.json")
            c = usertheme.load_config(p)
            self.assertEqual(len(c["entries"]), 3)
            self.assertEqual(c["extends"], "KooL Mocha")
            self.assertEqual(len(c["modes"]), 10)

if __name__ == "__main__":
    unittest.main()
