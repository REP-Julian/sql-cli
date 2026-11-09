import tempfile
import unittest
from pathlib import Path

from sqlcli.cli import save_output_to_file, save_sql_to_file


class SaveHelperTests(unittest.TestCase):
    def test_save_sql_to_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "query.sql"
            save_sql_to_file(str(target), "SELECT 1")
            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(encoding="utf-8").strip(), "SELECT 1;")

    def test_save_output_to_csv_and_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_target = Path(tmp_dir) / "results.csv"
            json_target = Path(tmp_dir) / "results.json"
            headers = ["id", "name"]
            rows = [(1, "Alice"), (2, "Bob")]

            save_output_to_file(str(csv_target), headers, rows)
            self.assertTrue(csv_target.exists())
            self.assertIn("Alice", csv_target.read_text(encoding="utf-8-sig"))

            save_output_to_file(str(json_target), headers, rows)
            self.assertTrue(json_target.exists())
            self.assertIn('"name": "Bob"', json_target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
