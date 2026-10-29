import unittest

from sqlcli.cli import _safe_csv_cell


class CsvSafetyTests(unittest.TestCase):
    def test_prefixes_formula_like_text(self):
        for value in ("=1+1", "+SUM(A1:A2)", "-1+2", "@SUM(A1:A2)", "\t=1+1"):
            with self.subTest(value=value):
                self.assertEqual(_safe_csv_cell(value), "'" + value)

    def test_preserves_non_formula_values_and_non_text_types(self):
        self.assertEqual(_safe_csv_cell("record name"), "record name")
        self.assertEqual(_safe_csv_cell(-12), -12)
        self.assertIsNone(_safe_csv_cell(None))


if __name__ == "__main__":
    unittest.main()
