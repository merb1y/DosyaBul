import unittest

from dosyabul.uninstall import InstalledProgram, search_installed_programs


def make_programs():
    return (
        InstalledProgram("1", "Stremio", "5.0", "Stremio", r'"C:\Program Files\Stremio\uninstall.exe" /S'),
        InstalledProgram("2", "Visual Studio Code", "1.9", "Microsoft", r"C:\Users\x\Uninstall.exe"),
        InstalledProgram("3", "Steam", "1.0", "Valve", "MsiExec.exe /X{1234-ABCD}"),
        InstalledProgram("4", "Not Defteri", "1.0", "Microsoft", "uninstall.exe"),
    )


class SearchInstalledProgramsTests(unittest.TestCase):
    def test_search_filters_by_name(self):
        results = search_installed_programs("stremio", make_programs())
        self.assertEqual([p.name for p in results], ["Stremio"])

    def test_search_matches_publisher(self):
        results = search_installed_programs("microsoft", make_programs())
        names = [p.name for p in results]
        self.assertIn("Visual Studio Code", names)
        self.assertIn("Not Defteri", names)

    def test_search_multiple_terms(self):
        results = search_installed_programs("visual code", make_programs())
        self.assertEqual([p.name for p in results], ["Visual Studio Code"])

    def test_empty_query_returns_empty(self):
        self.assertEqual(search_installed_programs("", make_programs()), ())
        self.assertEqual(search_installed_programs(None, make_programs()), ())

    def test_no_match_returns_empty(self):
        self.assertEqual(search_installed_programs("yok-boyle-program", make_programs()), ())

    def test_exact_match_ranks_first(self):
        results = search_installed_programs("steam", make_programs())
        self.assertEqual(results[0].name, "Steam")

    def test_result_limit(self):
        many = tuple(InstalledProgram(str(i), f"Program {i}", "", "", "x.exe") for i in range(30))
        results = search_installed_programs("program", many)
        self.assertEqual(len(results), 10)


if __name__ == "__main__":
    unittest.main()
