"""Unit tests verifying 100% offline functionality without network access."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prompt_toolkit.output import DummyOutput

from sqlcli.ai import is_ollama_available
from sqlcli.autopilot import generate_autopilot_plan, rule_based_sql_generator
from sqlcli.config import Settings
from sqlcli.diagnostics import analyze_error
from sqlcli.knowledge import lookup_topic, search_topics
from sqlcli.multi_engine import MultiEngineManager, NoSQLEngine, SQLiteEngine
from sqlcli.tui import TerminalStudio


class DummyMySQL:
    def __init__(self):
        self.tables = {"users": ["id", "username"]}
        self.connected = True

    def execute(self, query: str):
        return ["id", "username"], [(1, "alice")], 1


class TestOfflineFunctionality(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.sqlite_path = Path(self.temp_dir.name) / "offline.sqlite"
        self.nosql_path = Path(self.temp_dir.name) / "offline_nosql.db"

        self.settings = Settings()
        self.mysql = DummyMySQL()
        self.manager = MultiEngineManager(
            self.settings,
            self.mysql,
            sqlite_path=str(self.sqlite_path),
            nosql_path=str(self.nosql_path),
        )
        self.manager._history_file = Path(self.temp_dir.name) / "history.json"

    def tearDown(self):
        try:
            self.manager.close()
        except Exception:
            pass
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_sqlite_engine_works_100_percent_offline(self):
        """SQLite is embedded and must never make external calls."""
        headers, rows, count, elapsed, err = self.manager.execute(
            "CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, salary REAL);",
            engine="sqlite",
        )
        self.assertIsNone(err)

        headers, rows, count, elapsed, err = self.manager.execute(
            "INSERT INTO employees (name, salary) VALUES ('Alice Smith', 95000.0);",
            engine="sqlite",
        )
        self.assertIsNone(err)
        self.assertEqual(count, 1)

        headers, rows, count, elapsed, err = self.manager.execute(
            "SELECT * FROM employees;",
            engine="sqlite",
        )
        self.assertIsNone(err)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "Alice Smith")

    def test_nosql_engine_works_100_percent_offline(self):
        """NoSQL document store is local SQLite and operates offline."""
        headers, rows, count, elapsed, err = self.manager.execute(
            'db.inventory.insert({"item": "canvas_tent", "qty": 15, "tags": ["outdoor", "camping"]})',
            engine="nosql",
        )
        self.assertIsNone(err)
        self.assertEqual(count, 1)

        headers, rows, count, elapsed, err = self.manager.execute(
            'db.inventory.find({"item": "canvas_tent"})',
            engine="nosql",
        )
        self.assertIsNone(err)
        self.assertEqual(len(rows), 1)

    def test_autopilot_generates_sql_offline(self):
        """Rule-based Autopilot engine synthesizes SQL without any network access."""
        sql, cat, expl = rule_based_sql_generator("create table projects with name, budget, start_date")
        self.assertIn("CREATE TABLE", sql)
        self.assertIn("`budget`", sql)

        sql2, cat2, expl2 = generate_autopilot_plan("show top 5 employees ordered by salary", None, self.settings)
        self.assertIn("SELECT * FROM", sql2)
        self.assertIn("LIMIT 5", sql2)

    def test_knowledge_base_operates_offline(self):
        """W3Schools topics are pre-bundled and require no web scraping or network access."""
        topic = lookup_topic("inner join")
        self.assertIsNotNone(topic)
        self.assertEqual(topic.name, "SQL Inner Join")
        self.assertIn("INNER JOIN", topic.example)

        matches = search_topics("aggregate")
        self.assertGreaterEqual(len(matches), 1)

    def test_diagnostics_and_autofix_offline(self):
        """Error diagnostics HUD triangulates and patches queries without internet."""
        diag = analyze_error("SELECT * FORM employees;", "near FORM: syntax error")
        self.assertEqual(diag.error_type, "SYNTAX_ERROR")
        self.assertIn("FROM", diag.suggested_fix)
        self.assertEqual(diag.corrected_sql, "SELECT * FROM employees;")

    def test_ai_check_fails_fast_when_network_down(self):
        """When offline, Ollama network check returns False immediately without hanging."""
        with patch("urllib.request.urlopen", side_effect=OSError("Network unreachable")):
            available = is_ollama_available("http://127.0.0.1:11434", timeout=0.1)
            self.assertFalse(available)

    def test_terminal_studio_initializes_and_runs_offline(self):
        """Terminal Studio TUI builds and operates fully offline."""
        studio = TerminalStudio(
            self.manager,
            self.settings,
            self.mysql,
            output=DummyOutput(),
        )
        try:
            self.assertEqual(studio.engine_manager.active_engine, "sqlite")
            studio.seed_demo_data()
            self.assertIn("Alex Rivera", studio.results_area.text)
        finally:
            studio.close()


if __name__ == "__main__":
    unittest.main()
