import unittest

from sqlcli.cli import _is_complete_statement, _safe_csv_cell


class CsvSafetyTests(unittest.TestCase):
    def test_prefixes_formula_like_text(self):
        for value in ("=1+1", "+SUM(A1:A2)", "-1+2", "@SUM(A1:A2)", "\t=1+1"):
            with self.subTest(value=value):
                self.assertEqual(_safe_csv_cell(value), "'" + value)

    def test_preserves_non_formula_values_and_non_text_types(self):
        self.assertEqual(_safe_csv_cell("record name"), "record name")
        self.assertEqual(_safe_csv_cell(-12), -12)
        self.assertIsNone(_safe_csv_cell(None))


class CompleteStatementTests(unittest.TestCase):
    def test_empty_and_commands_are_complete(self):
        self.assertTrue(_is_complete_statement(""))
        self.assertTrue(_is_complete_statement("   "))
        self.assertTrue(_is_complete_statement(":tables"))
        self.assertTrue(_is_complete_statement(":use my_db"))

    def test_semicolon_terminated_statements(self):
        self.assertTrue(_is_complete_statement("SELECT 1;"))
        self.assertTrue(_is_complete_statement("CREATE TABLE students (\n  id INT\n);"))
        self.assertTrue(_is_complete_statement("SELECT * FROM users; -- comment"))

    def test_incomplete_multiline_statements(self):
        self.assertFalse(_is_complete_statement("Create table students("))
        self.assertFalse(_is_complete_statement("SELECT * FROM users"))
        self.assertFalse(_is_complete_statement("INSERT INTO students (id, name)"))


if __name__ == "__main__":
    unittest.main()
