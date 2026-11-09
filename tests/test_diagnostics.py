"""Unit tests for SQL error diagnostics and visual terminal error boxes."""

from __future__ import annotations

import unittest

from sqlcli.diagnostics import SQLDiagnostic, analyze_error, format_cli_error_box


class TestDiagnostics(unittest.TestCase):
    def test_database_missing_error(self):
        err = Exception("1046: No database selected")
        setattr(err, "errno", 1046)
        diag = analyze_error("SELECT * FROM users;", err)
        self.assertEqual(diag.error_type, "DATABASE_MISSING")
        self.assertEqual(diag.error_code, 1046)
        self.assertIn(":use", diag.suggested_fix)

    def test_mysql_table_not_found(self):
        err = Exception("Table 'school.students' doesn't exist")
        setattr(err, "errno", 1146)
        sql = "SELECT id, name\nFROM students\nWHERE id = 1;"
        diag = analyze_error(sql, err)
        self.assertEqual(diag.error_type, "TABLE_NOT_FOUND")
        self.assertEqual(diag.line_number, 2)
        self.assertEqual(diag.faulty_snippet, "students")

    def test_sqlite_table_not_found(self):
        err = Exception("no such table: courses")
        diag = analyze_error("SELECT * FROM courses;", err)
        self.assertEqual(diag.error_type, "TABLE_NOT_FOUND")
        self.assertEqual(diag.faulty_snippet, "courses")

    def test_column_not_found(self):
        err = Exception("Unknown column 'email_addr' in 'field list'")
        setattr(err, "errno", 1054)
        sql = "SELECT id, email_addr FROM users;"
        diag = analyze_error(sql, err)
        self.assertEqual(diag.error_type, "COLUMN_NOT_FOUND")
        self.assertEqual(diag.faulty_snippet, "email_addr")

    def test_syntax_error_typo_correction(self):
        err = Exception("You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near 'SELCT id FROM users' at line 1")
        setattr(err, "errno", 1064)
        diag = analyze_error("SELCT id FROM users;", err)
        self.assertEqual(diag.error_type, "SYNTAX_ERROR")
        self.assertIn("SELECT", diag.suggested_fix)

    def test_format_cli_error_box(self):
        diag = SQLDiagnostic(
            error_type="SYNTAX_ERROR",
            error_code=1064,
            line_number=1,
            column_offset=1,
            faulty_snippet="SELCT",
            message="near 'SELCT' at line 1",
            explanation="Typo in keyword",
            suggested_fix="Replace with SELECT",
        )
        box = format_cli_error_box(diag, "SELCT * FROM users;")
        self.assertIn("SQL EXECUTION ERROR (SYNTAX_ERROR)", box)
        self.assertIn("Line 1:", box)
        self.assertIn("^^^^^", box)
        self.assertIn("Replace with SELECT", box)

    def test_missing_quotes_on_string_literal(self):
        err = Exception("no such column: John")
        sql = "SELECT * FROM students WHERE name = John;"
        diag = analyze_error(sql, err)
        self.assertEqual(diag.error_type, "MISSING_QUOTES")
        self.assertIn("Missing quotes", diag.plain_summary)
        self.assertIn("single quotes", diag.rule_tip)
        self.assertIsNotNone(diag.corrected_sql)
        self.assertEqual(diag.corrected_sql, "SELECT * FROM students WHERE name = 'John';")

    def test_trailing_comma_in_create_table(self):
        err = Exception('near ")": syntax error')
        sql = "CREATE TABLE users (\n    id INT,\n    name TEXT,\n);"
        diag = analyze_error(sql, err)
        self.assertEqual(diag.error_type, "TRAILING_COMMA")
        self.assertIn("trailing comma", diag.plain_summary)
        self.assertIsNotNone(diag.corrected_sql)
        self.assertNotIn(",\n);", diag.corrected_sql)

    def test_unbalanced_parentheses(self):
        err = Exception("incomplete input")
        sql = "CREATE TABLE test (id INT, name TEXT"
        diag = analyze_error(sql, err)
        self.assertEqual(diag.error_type, "UNBALANCED_PARENTHESES")
        self.assertIn("Missing closing parenthesis", diag.plain_summary)
        self.assertTrue(diag.corrected_sql.endswith(");"))

    def test_table_already_exists(self):
        err = Exception("table students already exists")
        sql = "CREATE TABLE students (id INT);"
        diag = analyze_error(sql, err)
        self.assertEqual(diag.error_type, "TABLE_ALREADY_EXISTS")
        self.assertIn("IF NOT EXISTS", diag.suggested_fix)
        self.assertEqual(diag.corrected_sql, "CREATE TABLE IF NOT EXISTS students (id INT);")

    def test_duplicate_primary_key(self):
        err = Exception("UNIQUE constraint failed: students.id")
        sql = "INSERT INTO students (id, name) VALUES (1, 'Alice');"
        diag = analyze_error(sql, err)
        self.assertEqual(diag.error_type, "DUPLICATE_KEY")
        self.assertIn("Duplicate key", diag.plain_summary)

    def test_not_null_violation(self):
        err = Exception("NOT NULL constraint failed: students.name")
        sql = "INSERT INTO students (id) VALUES (1);"
        diag = analyze_error(sql, err)
        self.assertEqual(diag.error_type, "NOT_NULL_VIOLATION")
        self.assertIn("name", diag.plain_summary)

    def test_aggregate_in_where_clause(self):
        err = Exception("misuse of aggregate function COUNT()")
        sql = "SELECT * FROM students WHERE COUNT(id) > 1;"
        diag = analyze_error(sql, err)
        self.assertEqual(diag.error_type, "AGGREGATE_IN_WHERE")
        self.assertIn("HAVING", diag.suggested_fix)

    def test_clause_order_where_before_from(self):
        err = Exception('near "WHERE": syntax error')
        sql = "SELECT * WHERE id = 1 FROM students;"
        diag = analyze_error(sql, err)
        self.assertEqual(diag.error_type, "CLAUSE_ORDER_ERROR")
        self.assertIn("FROM", diag.suggested_fix)

    def test_mysql_offline_error(self):
        err = Exception("2003 (HY000): Can't connect to MySQL server on '127.0.0.1:3306'")
        sql = "SELECT 1;"
        diag = analyze_error(sql, err)
        self.assertEqual(diag.error_type, "DATABASE_OFFLINE")
        self.assertIn("SQLite", diag.suggested_fix)

    def test_nosql_json_syntax_error(self):
        err = Exception("JSONDecodeError: Expecting property name enclosed in double quotes")
        sql = "db.users.insert({name: 'Alice'});"
        diag = analyze_error(sql, err)
        self.assertEqual(diag.error_type, "NOSQL_SYNTAX_ERROR")
        self.assertIn("double quotes", diag.suggested_fix)


if __name__ == "__main__":
    unittest.main()
