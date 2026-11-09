"""Unit tests for the SQLite Studio Web Dashboard server."""

from __future__ import annotations

import json
import tempfile
import unittest
import urllib.request
from pathlib import Path

from sqlcli.config import Settings
from sqlcli.multi_engine import MultiEngineManager, NoSQLEngine, SQLiteEngine
from sqlcli.server import get_dashboard_html, start_studio_server


class DummyMySQL:
    def __init__(self):
        self.tables = {"users": ["id", "username"]}
        self.connected = True

    def execute(self, query: str):
        return ["id", "username"], [(1, "alice")], 1


class TestStudioServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.sqlite_path = Path(cls.temp_dir.name) / "test_workspace.sqlite"
        cls.nosql_path = Path(cls.temp_dir.name) / "test_nosql.db"

        cls.settings = Settings()
        cls.dummy_mysql = DummyMySQL()
        cls.manager = MultiEngineManager(
            cls.settings,
            cls.dummy_mysql,
            sqlite_path=str(cls.sqlite_path),
            nosql_path=str(cls.nosql_path),
        )
        cls.manager._history_file = Path(cls.temp_dir.name) / "history.json"

        # Start server without opening browser
        cls.thread, cls.port = start_studio_server(cls.manager, port=18080, open_browser=False)
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        try:
            cls.manager.close()
        except Exception:
            pass
        try:
            cls.temp_dir.cleanup()
        except Exception:
            pass

    def test_get_dashboard_page(self):
        with urllib.request.urlopen(f"{self.base_url}/") as response:
            self.assertEqual(response.status, 200)
            content = response.read().decode("utf-8")
            self.assertIn("SQLCLI Studio", content)
            self.assertIn("workspace.sqlite", content)

    def test_api_schema(self):
        with urllib.request.urlopen(f"{self.base_url}/api/schema?engine=sqlite") as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertIsInstance(data, dict)

    def test_api_topics(self):
        with urllib.request.urlopen(f"{self.base_url}/api/topics") as response:
            self.assertEqual(response.status, 200)
            topics = json.loads(response.read().decode("utf-8"))
            self.assertGreaterEqual(len(topics), 40)
            self.assertIn("select", topics)

    def test_api_execute_sqlite(self):
        payload = json.dumps({
            "query": "CREATE TABLE inventory (id INTEGER PRIMARY KEY, item TEXT);",
            "engine": "sqlite",
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/execute",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertIsNone(data["error"])

    def test_api_execute_error_diagnosis(self):
        # Query on non-existent table should return structured error diagnosis
        payload = json.dumps({
            "query": "SELECT * FROM non_existent_table_xyz;",
            "engine": "sqlite",
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/execute",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertIsNotNone(data["error"])
            self.assertIn("diagnostics", data)
            self.assertEqual(data["diagnostics"]["error_type"], "TABLE_NOT_FOUND")

    def test_api_demo_loading(self):
        payload = json.dumps({"engine": "sqlite"}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/demo",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertTrue(data.get("success"))

    def test_api_create_table_visual(self):
        payload = json.dumps({
            "engine": "sqlite",
            "table_name": "products_visual",
            "columns": [
                {"name": "id", "type": "INTEGER", "pk": True},
                {"name": "title", "type": "TEXT", "pk": False},
                {"name": "price", "type": "REAL", "pk": False},
            ]
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/create_table",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertTrue(data.get("success"))

    def test_api_insert_row_visual(self):
        payload = json.dumps({
            "engine": "sqlite",
            "table_name": "products_visual",
            "data": {"title": "Mechanical Keyboard", "price": 89.99}
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/insert_row",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertTrue(data.get("success"))

    def test_api_history(self):
        with urllib.request.urlopen(f"{self.base_url}/api/history") as response:
            self.assertEqual(response.status, 200)
            records = json.loads(response.read().decode("utf-8"))
            self.assertIsInstance(records, list)
            self.assertGreaterEqual(len(records), 2)


if __name__ == "__main__":
    unittest.main()
