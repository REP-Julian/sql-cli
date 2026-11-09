"""Unit tests for the Terminal Studio TUI."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from sqlcli.config import Settings
from sqlcli.multi_engine import MultiEngineManager, NoSQLEngine, SQLiteEngine
from sqlcli.tui import TerminalStudio


class DummyMySQL:
    def __init__(self):
        self.tables = {"users": ["id", "username"]}
        self.connected = True

    def execute(self, query: str):
        if "FAIL" in query:
            raise RuntimeError("1064: You have an error in your SQL syntax near 'FAIL'")
        return ["id", "username"], [(1, "alice")], 1


class TestTUI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.sqlite_path = Path(self.temp_dir.name) / "test_workspace.sqlite"
        self.nosql_path = Path(self.temp_dir.name) / "test_nosql.db"

        self.settings = Settings()
        self.mysql = DummyMySQL()
        self.manager = MultiEngineManager(
            self.settings,
            self.mysql,
            sqlite_path=str(self.sqlite_path),
            nosql_path=str(self.nosql_path),
        )
        self.manager._history_file = Path(self.temp_dir.name) / "history.json"

        self.studio = TerminalStudio(
            self.manager,
            self.settings,
            self.mysql,
            output=DummyOutput(),
        )

    def tearDown(self):
        try:
            self.manager.close()
        except Exception:
            pass
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_tui_initialization(self):
        self.assertEqual(self.studio.engine_manager.active_engine, "sqlite")
        self.assertIsNotNone(self.studio.layout)
        self.assertIn("SELECT", self.studio.editor_area.text)

    def test_tui_seed_demo_and_query(self):
        # Seed sample data
        self.manager.load_sample_data("sqlite")
        self.studio.refresh_schema()
        self.assertIn("students", self.studio.schema_area.text)

        # Run query on seeded data
        self.studio.editor_area.text = "SELECT id, name, gpa FROM students;"
        self.studio.run_current_query()
        self.assertIn("Alex Rivera", self.studio.results_area.text)
        self.assertIn("Query OK", self.studio.error_area.text)

    def test_tui_diagnostics_error_and_auto_fix(self):
        self.manager.load_sample_data("sqlite")

        # Intentional typo: 'FORM' instead of 'FROM'
        self.studio.editor_area.text = "SELECT * FORM students;"
        self.studio.run_current_query()

        # Check Error HUD has diagnostics
        self.assertIn("SYNTAX_ERROR", self.studio.error_area.text)
        self.assertIn("replace 'FORM' with 'FROM'", self.studio.error_area.text)

        # Apply Auto-Fix
        self.studio.apply_auto_fix()
        self.assertIn("FROM", self.studio.editor_area.text)
        self.assertNotIn("FORM", self.studio.editor_area.text)
        self.assertIn("Alex Rivera", self.studio.results_area.text)

    def test_tui_missing_quotes_auto_fix(self):
        self.manager.load_sample_data("sqlite")
        self.studio.editor_area.text = "SELECT * FROM students WHERE major = Business;"
        self.studio.run_current_query()

        self.assertIn("Missing quotes", self.studio.error_area.text)
        self.studio.apply_auto_fix()
        self.assertIn("'Business'", self.studio.editor_area.text)
        self.assertIn("Carlos Diaz", self.studio.results_area.text)

    def test_tui_tutor_cycling(self):
        initial_topic_idx = self.studio._tutor_topic_index
        self.studio.cycle_tutor_topic()
        self.assertGreater(self.studio._tutor_topic_index, initial_topic_idx)
        self.assertIn("Topic:", self.studio.tutor_area.text)
        self.assertGreater(len(self.studio.editor_area.text.strip()), 0)


    def test_tui_tab_switching(self):
        self.studio.switch_tab("history")
        self.assertEqual(self.studio.active_sidebar_tab, "history")
        self.studio.switch_tab("tutor")
        self.assertEqual(self.studio.active_sidebar_tab, "tutor")
        self.studio.switch_tab("schema")
        self.assertEqual(self.studio.active_sidebar_tab, "schema")

    def test_tui_export_csv_and_json(self):
        self.manager.load_sample_data("sqlite")
        self.studio.editor_area.text = "SELECT id, name FROM students;"
        self.studio.run_current_query()

        self.studio.save_results_dialog()
        self.assertIn("Exported", self.studio.status_message)

        csv_file = Path("results.csv")
        json_file = Path("results.json")
        self.assertTrue(csv_file.exists())
        self.assertTrue(json_file.exists())
        # Clean up exported files
        csv_file.unlink(missing_ok=True)
        json_file.unlink(missing_ok=True)

    def test_tui_format_sql(self):
        self.studio.editor_area.text = "select id, name from students where id = 1 group by name order by id limit 5;"
        self.studio.format_editor_sql()
        self.assertIn("SELECT", self.studio.editor_area.text)
        self.assertIn("FROM", self.studio.editor_area.text)
        self.assertIn("WHERE", self.studio.editor_area.text)
        self.assertIn("ORDER BY", self.studio.editor_area.text)

    def test_tui_toggle_maximize_results(self):
        self.assertFalse(self.studio.is_results_maximized)
        self.studio.toggle_maximize_results()
        self.assertTrue(self.studio.is_results_maximized)
        self.studio.toggle_maximize_results()
        self.assertFalse(self.studio.is_results_maximized)

    def test_tui_history_selection(self):
        self.manager.load_sample_data("sqlite")
        self.studio.editor_area.text = "SELECT name FROM students LIMIT 1;"
        self.studio.run_current_query()

        self.studio.switch_tab("history")
        self.assertGreaterEqual(len(self.studio._history_records), 1)

        # Clear editor and load from history
        self.studio.editor_area.text = ""
        self.studio.load_selected_history_item()
        self.assertIn("SELECT", self.studio.editor_area.text)


if __name__ == "__main__":
    unittest.main()
