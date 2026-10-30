import unittest

from prompt_toolkit.document import Document

from sqlcli.completion import SQLCompleter


class _Database:
    tables = {"students": ["student_id", "name"]}
    database_names = []


class _Plugins:
    commands = []

    @staticmethod
    def completions(_text):
        return []


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.completer = SQLCompleter(_Database(), _Plugins())

    def _suggestions(self, text):
        return [item.text for item in self.completer.get_completions(Document(text), None)]

    def test_delete_clause_suggests_from_as_one_word(self):
        suggestions = self._suggestions("what command to delete a ")
        self.assertIn("FROM", suggestions)
        self.assertNotIn("F", suggestions)
        self.assertNotIn("R", suggestions)

    def test_clause_suggestions_are_words_not_characters(self):
        for text, expected in (("SELECT ", "DISTINCT"), ("FROM students ", "JOIN"), ("WHERE ", "AND")):
            with self.subTest(text=text):
                suggestions = self._suggestions(text)
                self.assertIn(expected, suggestions)
                self.assertFalse({"F", "R", "O", "M"}.intersection(suggestions))


if __name__ == "__main__":
    unittest.main()
