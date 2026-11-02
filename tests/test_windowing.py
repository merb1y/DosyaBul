import unittest

from dosyabul.windowing import WorkArea


class WorkAreaTests(unittest.TestCase):
    def test_width_and_height(self):
        area = WorkArea(10, 20, 110, 220)
        self.assertEqual(area.width, 100)
        self.assertEqual(area.height, 200)

    def test_zero_size(self):
        area = WorkArea(0, 0, 0, 0)
        self.assertEqual(area.width, 0)
        self.assertEqual(area.height, 0)


if __name__ == "__main__":
    unittest.main()
