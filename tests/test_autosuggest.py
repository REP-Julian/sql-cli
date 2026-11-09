import unittest
from prompt_toolkit.document import Document
from sqlcli.autosuggest import SQLAutoSuggest


class _MockDB:
    tables = {"students": ["id", "name"], "courses": ["id", "title"]}
    database_names = ["school_db"]


class AutoSuggestTests(unittest.TestCase):
    def setUp(self):
        self.suggest = SQLAutoSuggest(_MockDB())

    def test_select_suggests_table(self):
        doc = Document("SELECT")
        res = self.suggest.get_suggestion(None, doc)
        self.assertIsNotNone(res)
        self.assertIn("FROM `students`", res.text)

    def test_create_table_suggests_skeleton(self):
        doc = Document("CREATE TABLE")
        res = self.suggest.get_suggestion(None, doc)
        self.assertIsNotNone(res)
        self.assertIn("`id` INT AUTO_INCREMENT PRIMARY KEY", res.text)

    def test_use_suggests_database(self):
        doc = Document(":USE")
        res = self.suggest.get_suggestion(None, doc)
        self.assertIsNotNone(res)
        self.assertIn("school_db", res.text)


if __name__ == "__main__":
    unittest.main()
