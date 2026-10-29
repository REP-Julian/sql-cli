import unittest

from sqlcli.sql_safety import inspect_sql


class SQLSafetyTests(unittest.TestCase):
    def test_delete_with_targeted_where_requires_confirmation(self):
        result = inspect_sql("DELETE FROM records WHERE record_id = 5;")
        self.assertEqual(result.verb, "DELETE")
        self.assertTrue(result.requires_confirmation)
        self.assertFalse(result.missing_where)

    def test_where_inside_comment_does_not_make_delete_safe(self):
        result = inspect_sql("DELETE FROM records /* WHERE record_id = 5 */;")
        self.assertTrue(result.requires_confirmation)
        self.assertTrue(result.missing_where)

    def test_where_inside_string_does_not_make_update_safe(self):
        result = inspect_sql("UPDATE records SET note = 'WHERE record_id = 5';")
        self.assertTrue(result.requires_confirmation)
        self.assertTrue(result.missing_where)

    def test_cte_delete_is_still_confirmed_and_requires_where(self):
        result = inspect_sql("WITH target AS (SELECT record_id FROM records) DELETE FROM records;")
        self.assertEqual(result.verb, "DELETE")
        self.assertTrue(result.requires_confirmation)
        self.assertTrue(result.missing_where)

    def test_cte_delete_with_real_where_is_targeted(self):
        result = inspect_sql(
            "WITH target AS (SELECT record_id FROM records) "
            "DELETE FROM records WHERE record_id = 5;"
        )
        self.assertEqual(result.verb, "DELETE")
        self.assertTrue(result.requires_confirmation)
        self.assertFalse(result.missing_where)

    def test_words_inside_select_string_are_not_classified_as_mutation(self):
        result = inspect_sql("SELECT 'DELETE FROM records' AS example;")
        self.assertEqual(result.verb, "SELECT")
        self.assertFalse(result.requires_confirmation)
        self.assertFalse(result.missing_where)

    def test_select_into_outfile_requires_confirmation(self):
        result = inspect_sql("SELECT record_id FROM records INTO OUTFILE 'export.csv';")
        self.assertEqual(result.verb, "SELECT")
        self.assertTrue(result.requires_confirmation)

    def test_mysql_executable_comment_cannot_hide_delete_from_safety_check(self):
        result = inspect_sql("/*!50000 DELETE FROM records */;")
        self.assertEqual(result.verb, "DELETE")
        self.assertTrue(result.requires_confirmation)
        self.assertTrue(result.missing_where)

    def test_mysql_executable_comment_cannot_hide_select_file_write(self):
        result = inspect_sql("SELECT /*! INTO OUTFILE '/tmp/export.csv' */ 1;")
        self.assertTrue(result.requires_confirmation)

    def test_mariadb_executable_comment_cannot_hide_delete_from_safety_check(self):
        result = inspect_sql("/*M!100100 DELETE FROM records */;")
        self.assertEqual(result.verb, "DELETE")
        self.assertTrue(result.requires_confirmation)
        self.assertTrue(result.missing_where)

    def test_multiple_statements_are_detected_but_semicolons_in_strings_are_not(self):
        self.assertTrue(inspect_sql("SELECT 1; DELETE FROM records;").multiple_statements)
        self.assertFalse(inspect_sql("SELECT ';' AS punctuation;").multiple_statements)


if __name__ == "__main__":
    unittest.main()
