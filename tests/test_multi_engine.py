"""Unit tests for MultiEngineManager, SQLiteEngine, and NoSQLEngine."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlcli.config import Settings
from sqlcli.multi_engine import MultiEngineManager, NoSQLEngine, SQLiteEngine


class DummyMySQL:
    def __init__(self):
        self.tables = {"users": ["id", "username"]}
        self.connected = True

    def execute(self, query: str):
        if "FAIL" in query:
            raise RuntimeError("MySQL syntax failure")
        return ["id", "username"], [(1, "alice")], 1


class TestMultiEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.sqlite_path = Path(self.temp_dir.name) / "test_workspace.sqlite"
        self.nosql_path = Path(self.temp_dir.name) / "test_nosql.db"

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_sqlite_engine_ddl_and_dml(self):
        engine = SQLiteEngine(str(self.sqlite_path))
        try:
            # CREATE TABLE
            headers, rows, count = engine.execute(
                "CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT, gpa REAL);"
            )
            self.assertIsNone(headers)

            # INSERT
            headers, rows, count = engine.execute(
                "INSERT INTO students (name, gpa) VALUES ('John Doe', 3.85);"
            )
            self.assertEqual(count, 1)

            # SELECT
            headers, rows, count = engine.execute("SELECT id, name, gpa FROM students;")
            self.assertEqual(headers, ["id", "name", "gpa"])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][1], "John Doe")
            self.assertEqual(rows[0][2], 3.85)

            # Schema inspection
            schema = engine.get_schema()
            self.assertIn("students", schema)
            self.assertEqual(schema["students"], ["id", "name", "gpa"])
        finally:
            engine.close()

    def test_nosql_engine_document_operations(self):
        engine = NoSQLEngine(str(self.nosql_path))
        try:
            # Insert document
            doc_id = engine.insert("orders", {"customer": "Alice", "total": 99.50})
            self.assertGreaterEqual(doc_id, 1)

            # Find document
            docs = engine.find("orders", {"customer": "Alice"})
            self.assertEqual(len(docs), 1)
            self.assertEqual(docs[0]["customer"], "Alice")
            self.assertEqual(docs[0]["total"], 99.50)

            # Command: db.<collection>.insert(...)
            headers, rows, count = engine.execute_command('db.products.insert({"name": "Laptop", "price": 1200})')
            self.assertEqual(count, 1)

            # Command: db.<collection>.find()
            headers, rows, count = engine.execute_command("db.products.find()")
            self.assertIn("name", headers)
            self.assertEqual(count, 1)

            # Command: show collections
            headers, rows, count = engine.execute_command("show collections;")
            collection_names = [r[0] for r in rows]
            self.assertIn("orders", collection_names)
            self.assertIn("products", collection_names)

            # Command: db.<collection>.delete(...)
            headers, rows, count = engine.execute_command('db.products.delete({"name": "Laptop"})')
            self.assertEqual(count, 1)
            self.assertEqual(len(engine.find("products")), 0)
        finally:
            engine.close()

    def test_multi_engine_manager_switching_and_history(self):
        settings = Settings()
        dummy_mysql = DummyMySQL()
        manager = MultiEngineManager(
            settings,
            dummy_mysql,
            sqlite_path=str(self.sqlite_path),
            nosql_path=str(self.nosql_path),
        )
        manager._history_file = Path(self.temp_dir.name) / "history.json"

        try:
            # 1. Execute on SQLite
            manager.active_engine = "sqlite"
            headers, rows, count, elapsed_ms, err = manager.execute(
                "CREATE TABLE logs (id INTEGER PRIMARY KEY, msg TEXT);"
            )
            self.assertIsNone(err)
            self.assertGreater(elapsed_ms, 0)

            # 2. Execute on NoSQL
            manager.active_engine = "nosql"
            headers, rows, count, elapsed_ms, err = manager.execute(
                'db.events.insert({"type": "login", "user": "alice"})'
            )
            self.assertIsNone(err)
            self.assertEqual(count, 1)

            # 3. Execute on MySQL
            manager.active_engine = "mysql"
            headers, rows, count, elapsed_ms, err = manager.execute("SELECT * FROM users;")
            self.assertIsNone(err)
            self.assertEqual(headers, ["id", "username"])

            # 4. Check logged history
            history = manager.load_history()
            self.assertEqual(len(history), 3)
            self.assertEqual(history[0]["engine"], "sqlite")
            self.assertEqual(history[1]["engine"], "nosql")
            self.assertEqual(history[2]["engine"], "mysql")
            self.assertEqual(history[0]["status"], "SUCCESS")
        finally:
            manager.close()


if __name__ == "__main__":
    unittest.main()
