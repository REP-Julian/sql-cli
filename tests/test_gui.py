"""Unit tests for the Native PyQt6 Desktop Studio."""

from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure Qt runs headlessly in test environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from sqlcli.config import Settings
from sqlcli.gui import CreateTableDialog, SQLStudioWindow
from sqlcli.multi_engine import MultiEngineManager


class DummyMySQL:
    """Mock MySQL connection for offline tests."""

    def __init__(self) -> None:
        self.tables = {"users": ["id", "username"]}
        self.connected = True

    def execute(self, query: str):
        if "FAIL" in query:
            raise RuntimeError("1064: You have an error in your SQL syntax near 'FAIL'")
        return ["id", "username"], [(1, "alice")], 1


class TestPyQt6DesktopStudio(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication(["sqlcli_test"])

    def setUp(self) -> None:
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

        self.window = SQLStudioWindow(
            self.manager,
            self.settings,
            self.mysql,
        )
        # Ensure tests run in isolated SQLite mode by default
        self.window.engine_combo.setCurrentIndex(0)
        self.window._on_engine_changed(0)
        self.window.show()

    def tearDown(self) -> None:
        if hasattr(self.window, "health_timer"):
            self.window.health_timer.stop()
        self.window.close()
        self.manager.close()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_window_initialization(self) -> None:
        self.assertIn("SQLCLI Desktop Studio", self.window.windowTitle())
        self.assertIsNotNone(self.window.editor)
        self.assertIsNotNone(self.window.table_widget)
        self.assertIsNotNone(self.window.schema_tree)
        self.assertIsNotNone(self.window.history_list)
        self.assertFalse(self.window.error_frame.isVisible())
        self.assertEqual(self.window.engine_combo.currentIndex(), 0)

    def test_seed_demo_data_and_table_population(self) -> None:
        self.window.seed_demo_data()
        self.assertEqual(self.window.table_widget.rowCount(), 5)
        self.assertEqual(self.window.table_widget.columnCount(), 6)
        first_cell = self.window.table_widget.item(0, 1)
        self.assertIsNotNone(first_cell)
        self.assertEqual(first_cell.text(), "Diana Prince")

        # Verify schema tree has top level database node and tables
        self.assertGreaterEqual(self.window.schema_tree.topLevelItemCount(), 1)
        root = self.window.schema_tree.topLevelItem(0)
        self.assertIn("Database [SQLITE]", root.text(0))

    def test_run_valid_query_and_history(self) -> None:
        self.window.seed_demo_data()
        self.window.editor.setPlainText("SELECT name, gpa FROM students WHERE gpa > 3.9;")
        self.window.run_query()

        self.assertEqual(self.window.table_widget.rowCount(), 2)
        self.assertEqual(self.window.table_widget.columnCount(), 2)
        self.assertFalse(self.window.error_frame.isVisible())
        self.assertGreaterEqual(self.window.history_list.count(), 1)

    def test_error_hud_and_auto_fix(self) -> None:
        self.window.seed_demo_data()
        self.window.editor.setPlainText("SELEC id, name FROM students;")
        self.window.run_query()

        self.assertTrue(self.window.error_frame.isVisible())
        self.assertIn("Typo in keyword", self.window.error_problem.text())
        self.assertTrue(self.window.auto_fix_btn.isEnabled())

        # Trigger auto-fix
        self.window.apply_auto_fix()
        self.assertIn("SELECT id, name FROM students;", self.window.editor.toPlainText())
        self.assertFalse(self.window.error_frame.isVisible())
        self.assertEqual(self.window.table_widget.rowCount(), 5)

    def test_format_sql(self) -> None:
        self.window.editor.setPlainText("select id from students where id = 1 order by id desc;")
        self.window.format_sql()
        formatted = self.window.editor.toPlainText()
        self.assertIn("SELECT", formatted)
        self.assertIn("FROM", formatted)
        self.assertIn("WHERE", formatted)
        self.assertIn("ORDER BY", formatted)

    def test_engine_switching(self) -> None:
        self.window.engine_combo.setCurrentIndex(2)  # Switch to NoSQL
        self.assertEqual(self.manager.active_engine, "nosql")
        self.assertIn("NOSQL", self.window.engine_indicator.text())

        self.window.engine_combo.setCurrentIndex(0)  # Switch to SQLite
        self.assertEqual(self.manager.active_engine, "sqlite")
        self.assertIn("SQLITE", self.window.engine_indicator.text())

    def test_w3schools_tutor_selection(self) -> None:
        where_index = -1
        for i in range(self.window.topic_combo.count()):
            key = (self.window.topic_combo.itemData(i) or "").lower()
            text = self.window.topic_combo.itemText(i).lower()
            if key == "where" or "where" in text:
                where_index = i
                break
        self.assertGreaterEqual(where_index, 0)
        self.window.topic_combo.setCurrentIndex(where_index)
        self.assertIn("WHERE", self.window.tutor_summary.text().upper())
        self.window._load_tutor_example_into_editor()
        self.assertIn("WHERE", self.window.editor.toPlainText().upper())

    def test_advanced_sql_tutor_suite(self) -> None:
        self.window.seed_demo_data()

        # 1. Test search filter
        self.window.tutor_search.setText("window")
        self.assertGreaterEqual(self.window.topic_combo.count(), 1)
        self.assertIn("Window", self.window.tutor_title.text())
        self.assertIn("ROW_NUMBER", self.window.tutor_syntax.toPlainText())
        self.assertIn("RANK", self.window.tutor_example.toPlainText())

        # 2. Test live run
        self.window.topic_combo.setCurrentIndex(0)
        self.window._run_tutor_example_live()
        self.assertEqual(self.window.main_stack.currentIndex(), 1)

        # 3. Test adapt to active table
        self.window.tutor_search.setText("distinct")
        self.window.active_table_name = "students"
        self.window._adapt_tutor_example_to_active_table()
        editor_text = self.window.editor.toPlainText()
        self.assertIn("`students`", editor_text)

        # 4. Test practice mission loading
        self.window._load_challenge_into_editor()
        self.assertIn("SQL TUTOR MISSION", self.window.editor.toPlainText())

        # 5. Test show solution
        self.window._show_tutor_solution()
        self.assertIn("Solution", self.window.editor.toPlainText())

        # 6. Test mastery check
        self.window.tutor_mark_done_check.setChecked(True)
        self.assertIn("select-distinct", self.window.mastered_topics)
        self.assertIn("1 Mastered", self.window.tutor_count_label.text())

        # 7. Test prev/next navigation
        self.window.tutor_search.setText("")
        self.window.tutor_cat_combo.setCurrentText("Basics")
        count = self.window.topic_combo.count()
        self.assertGreater(count, 1)
        self.window.topic_combo.setCurrentIndex(0)
        self.window._next_tutor_topic()
        self.assertEqual(self.window.topic_combo.currentIndex(), 1)
        self.window._prev_tutor_topic()
        self.assertEqual(self.window.topic_combo.currentIndex(), 0)

        # 8. Test DDL, DML, DCL, TCL category dropdown filtering
        self.window.tutor_cat_combo.setCurrentText("DDL (Data Definition)")
        self.assertGreaterEqual(self.window.topic_combo.count(), 5)
        self.assertIn("DDL", self.window.tutor_category_chip.text())

        self.window.tutor_cat_combo.setCurrentText("DML (Data Manipulation)")
        self.assertGreaterEqual(self.window.topic_combo.count(), 4)
        self.assertIn("DML", self.window.tutor_category_chip.text())

        self.window.tutor_cat_combo.setCurrentText("DCL (Data Control)")
        self.assertGreaterEqual(self.window.topic_combo.count(), 5)
        self.assertIn("DCL", self.window.tutor_category_chip.text())

        self.window.tutor_cat_combo.setCurrentText("TCL (Transaction Control)")
        self.assertGreaterEqual(self.window.topic_combo.count(), 4)
        self.assertIn("TCL", self.window.tutor_category_chip.text())

    def test_export_csv_and_json(self) -> None:
        self.window.seed_demo_data()
        csv_file = Path(self.temp_dir.name) / "export_test.csv"
        json_file = Path(self.temp_dir.name) / "export_test.json"

        # Mock QFileDialog to return temp paths
        with patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=(str(csv_file), "csv")):
            with patch("PyQt6.QtWidgets.QMessageBox.information"):
                self.window.export_csv()
        self.assertTrue(csv_file.exists())
        with csv_file.open(encoding="utf-8") as f:
            reader = list(csv.reader(f))
            self.assertEqual(len(reader), 6)  # 1 header + 5 rows

        with patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=(str(json_file), "json")):
            with patch("PyQt6.QtWidgets.QMessageBox.information"):
                self.window.export_json()
        self.assertTrue(json_file.exists())
        data = json.loads(json_file.read_text(encoding="utf-8"))
        self.assertEqual(len(data), 5)

    def test_quick_template_chips(self) -> None:
        self.window.seed_demo_data()
        self.window._apply_template("SELECT major, COUNT(*) AS count FROM students GROUP BY major;\n", True)
        self.assertGreaterEqual(self.window.table_widget.rowCount(), 1)
        self.assertIn("students", self.window.editor.toPlainText())

    def test_realtime_table_filter(self) -> None:
        self.window.seed_demo_data()
        self.assertEqual(self.window.table_widget.rowCount(), 5)

        # Filter by "Diana"
        self.window.table_filter_input.setText("Diana")
        hidden_count = sum(self.window.table_widget.isRowHidden(r) for r in range(5))
        self.assertEqual(hidden_count, 4)  # 4 hidden, 1 visible
        self.assertIn("Displaying 1 of 5", self.window.results_count_label.text())

        # Clear filter
        self.window.table_filter_input.setText("")
        hidden_count_cleared = sum(self.window.table_widget.isRowHidden(r) for r in range(5))
        self.assertEqual(hidden_count_cleared, 0)

    def test_copy_entire_table_tsv(self) -> None:
        self.window.seed_demo_data()
        self.window._copy_entire_table_tsv()
        clipboard_text = QApplication.clipboard().text()
        self.assertIn("name", clipboard_text)
        self.assertIn("Diana Prince", clipboard_text)

    def test_column_double_click_insertion(self) -> None:
        self.window.seed_demo_data()
        self.window.editor.setPlainText("SELECT ")
        # Find a column item in the schema tree
        col_item = None
        for i in range(self.window.schema_tree.topLevelItemCount()):
            top = self.window.schema_tree.topLevelItem(i)
            for j in range(top.childCount()):
                child = top.child(j)
                for k in range(child.childCount()):
                    gc = child.child(k)
                    data = gc.data(0, Qt.ItemDataRole.UserRole) or ""
                    if data.startswith("col:"):
                        col_item = gc
                        break
                if col_item:
                    break
            if col_item:
                break

        self.assertIsNotNone(col_item)
        # Double clicking column should NEVER corrupt query in editor
        self.window._on_schema_item_double_clicked(col_item, 0)
        self.assertEqual(self.window.editor.toPlainText(), "SELECT ")
        self.assertIn("Column `id` selected", self.window.status_label.text())

    def test_error_tutorial_button(self) -> None:
        self.window.seed_demo_data()
        self.window.editor.setPlainText("SELEC id FROM students;")
        self.window.run_query()

        self.window._open_tutorial_for_error()
        self.assertEqual(self.window.sidebar_tabs.currentIndex(), 2)  # Switched to Tutor tab

    def test_completer_words_populated(self) -> None:
        self.window.seed_demo_data()
        words = self.window.completer_model.stringList()
        self.assertIn("SELECT", words)
        self.assertIn("COUNT(*)", words)
        self.assertIn("VARCHAR(255)", words)
        self.assertIn("students", words)
        self.assertIn("courses", words)
        self.assertIn("students.name", words)

        # Autopilot completer checks
        autopilot_prompts = self.window.autopilot_model.stringList()
        self.assertTrue(any("students" in p for p in autopilot_prompts))
        self.assertTrue(any("count records in" in p for p in autopilot_prompts))

    def test_code_editor_token_and_completion_commit(self) -> None:
        self.window.seed_demo_data()
        self.window.editor.setPlainText("SELECT stu")
        tc = self.window.editor.textCursor()
        tc.movePosition(tc.MoveOperation.End)
        self.window.editor.setTextCursor(tc)

        token = self.window.editor.text_under_cursor()
        self.assertEqual(token, "stu")

        # Dotted token under cursor
        self.window.editor.setPlainText("SELECT students.na")
        tc = self.window.editor.textCursor()
        tc.movePosition(tc.MoveOperation.End)
        self.window.editor.setTextCursor(tc)
        dotted_token = self.window.editor.text_under_cursor()
        self.assertEqual(dotted_token, "students.na")

        # Test insert completion replacing prefix
        self.window.editor._insert_completion("students.name")
        self.assertIn("SELECT students.name", self.window.editor.toPlainText())

    def test_dynamic_quick_actions(self) -> None:
        self.window.seed_demo_data()
        # Test view top data
        self.window._action_view_top_data()
        self.assertIn("SELECT * FROM `students` LIMIT 50;", self.window.editor.toPlainText())
        self.assertEqual(self.window.table_widget.rowCount(), 5)

        # Test count rows
        self.window._action_count_rows()
        self.assertIn("COUNT(*)", self.window.editor.toPlainText())

        # Test describe structure
        self.window._action_describe_table()
        self.assertIn("PRAGMA table_info", self.window.editor.toPlainText())

        # Test insert template
        self.window._action_insert_template()
        self.assertIn("INSERT INTO `students`", self.window.editor.toPlainText())

    def test_realtime_health_timer(self) -> None:
        self.assertTrue(self.window.health_timer.isActive())
        self.window._check_engine_health_realtime()
        self.assertIn("MySQL", self.window.engine_badge.text())

    def test_realtime_mutation_grid_refresh(self) -> None:
        self.window.seed_demo_data()
        self.assertEqual(self.window.table_widget.rowCount(), 5)

        # Run an INSERT mutation
        self.window.editor.setPlainText(
            "INSERT INTO students (name, email, major, gpa, enrollment_year) "
            "VALUES ('New Realtime Student', 'realtime@test.com', 'Cybersecurity', 4.0, 2026);"
        )
        self.window.run_query()

        # Results grid should immediately refresh and show the 6th student in real time!
        self.assertEqual(self.window.table_widget.rowCount(), 6)
        self.assertIn("New Realtime Student", self.window.table_widget.item(5, 1).text())
        self.assertIn("Showing `students`", self.window.results_count_label.text())

    def test_mode_switching(self) -> None:
        self.window.switch_to_data_view()
        self.assertEqual(self.window.main_stack.currentIndex(), 0)

        self.window.switch_to_sql_view()
        self.assertEqual(self.window.main_stack.currentIndex(), 1)

    def test_table_click_switches_to_data_view_and_loads(self) -> None:
        self.window.seed_demo_data()
        self.window.switch_to_sql_view()
        self.assertEqual(self.window.main_stack.currentIndex(), 1)

        # Find 'students' table item in schema tree
        table_item = None
        for i in range(self.window.schema_tree.topLevelItemCount()):
            top = self.window.schema_tree.topLevelItem(i)
            for j in range(top.childCount()):
                child = top.child(j)
                data = child.data(0, Qt.ItemDataRole.UserRole) or ""
                if "students" in data:
                    table_item = child
                    break
            if table_item:
                break

        self.assertIsNotNone(table_item)
        prev_editor_sql = self.window.editor.toPlainText()

        # Single click on table item must switch to Data View and load data without corrupting editor
        self.window._on_schema_item_clicked(table_item, 0)
        self.assertEqual(self.window.main_stack.currentIndex(), 0)
        self.assertEqual(self.window.table_widget.rowCount(), 5)
        self.assertEqual(self.window.editor.toPlainText(), prev_editor_sql)

    def test_add_record_dialog_direct(self) -> None:
        self.window.seed_demo_data()
        self.assertEqual(self.window.table_widget.rowCount(), 5)

        with patch("sqlcli.gui.AddRecordDialog.exec", return_value=1):  # QDialog.DialogCode.Accepted
            with patch("sqlcli.gui.AddRecordDialog.get_record_data", return_value={
                "name": "Grace Hopper",
                "email": "grace@navy.mil",
                "major": "Computer Science",
                "gpa": "4.0",
                "enrollment_year": "2026",
            }):
                self.window.add_new_record()

        self.assertEqual(self.window.table_widget.rowCount(), 6)
        found = any(
            self.window.table_widget.item(r, 1) and self.window.table_widget.item(r, 1).text() == "Grace Hopper"
            for r in range(self.window.table_widget.rowCount())
        )
        self.assertTrue(found)

    def test_delete_selected_record_direct(self) -> None:
        self.window.seed_demo_data()
        self.assertEqual(self.window.table_widget.rowCount(), 5)

        # Select first row in table
        self.window.table_widget.selectRow(0)
        with patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            self.window.delete_selected_records()

        self.assertEqual(self.window.table_widget.rowCount(), 4)

    def test_inline_cell_editing(self) -> None:
        self.window.seed_demo_data()
        self.window.load_table_data("students")
        self.assertGreaterEqual(self.window.table_widget.rowCount(), 1)

        # Simulate user entering cell (0, 1) ('name' column) and changing value
        self.window._on_table_cell_entered(0, 1)
        item = self.window.table_widget.item(0, 1)
        self.assertIsNotNone(item)
        old_val = item.text()

        item.setText(f"{old_val} Modified")
        # Ensure value in database is updated
        cursor = self.manager.sqlite.connection.cursor()
        cursor.execute("SELECT name FROM students WHERE id = 1;")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertIn("Modified", row[0])

    def test_inline_pk_column_editing(self) -> None:
        self.window.seed_demo_data()
        self.window.load_table_data("students")

        # Simulate editing PK column (col 0: 'id') from '1' to '99'
        self.window._on_table_cell_entered(0, 0)
        pk_item = self.window.table_widget.item(0, 0)
        self.assertIsNotNone(pk_item)
        pk_item.setText("99")

        cursor = self.manager.sqlite.connection.cursor()
        cursor.execute("SELECT name FROM students WHERE id = 99;")
        row = cursor.fetchone()
        self.assertIsNotNone(row)

    def test_nosql_crud_in_gui(self) -> None:
        # Switch to NoSQL engine
        self.window.engine_combo.setCurrentIndex(2)
        self.window._on_engine_changed(2)
        self.manager.load_sample_data("nosql")
        self.window.load_table_data("students")
        self.assertEqual(self.window.table_widget.rowCount(), 3)

        # Inline edit a NoSQL document cell
        name_col = next(
            c for c in range(self.window.table_widget.columnCount())
            if self.window.table_widget.horizontalHeaderItem(c).text() == "name"
        )
        self.window._on_table_cell_entered(0, name_col)
        self.window.table_widget.item(0, name_col).setText("NoSQL Edited Student")
        self.window.load_table_data("students")
        self.assertEqual(self.window.table_widget.item(0, name_col).text(), "NoSQL Edited Student")

        # Delete selected NoSQL document
        self.window.table_widget.selectRow(0)
        with patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            self.window.delete_selected_records()
        self.assertEqual(self.window.table_widget.rowCount(), 2)

    def test_multi_statement_execution_and_autopilot_sqlite(self) -> None:
        # Multi-statement script in SQLite
        self.window.editor.setPlainText(
            "CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT);\n"
            "INSERT INTO items (title) VALUES ('Laptop'), ('Keyboard');\n"
            "SELECT * FROM items;"
        )
        self.window.run_query()
        self.assertFalse(self.window.error_frame.isVisible())
        self.assertEqual(self.window.table_widget.rowCount(), 2)

        # Autopilot CREATE TABLE in SQLite mode (must use SQLite syntax, not MySQL ENGINE=InnoDB)
        self.window.autopilot_input.setText("create table tasks with title and status")
        self.window.run_autopilot()
        self.assertFalse(self.window.error_frame.isVisible())
        self.assertIn("tasks", self.manager.sqlite.get_schema())

    def test_prompt_create_and_drop_database_gui(self) -> None:
        # Switch to MySQL mode (using DummyMySQL)
        self.window.engine_combo.setCurrentIndex(1)
        self.window._on_engine_changed(1)

        # Create new database
        with patch("PyQt6.QtWidgets.QInputDialog.getText", return_value=("test_new_db", True)):
            self.window.prompt_create_database()
        self.assertEqual(self.settings.database, "test_new_db")

        # Drop database with confirmation
        with patch("PyQt6.QtWidgets.QMessageBox.warning", return_value=QMessageBox.StandardButton.Yes):
            with patch("PyQt6.QtWidgets.QMessageBox.information"):
                self.window.prompt_drop_database("test_new_db")
        self.assertIn("dropped", self.window.status_label.text())

    def test_drop_database_system_protection(self) -> None:
        self.window.engine_combo.setCurrentIndex(1)
        self.window._on_engine_changed(1)

        # Attempt to drop system database 'mysql'
        with patch("PyQt6.QtWidgets.QMessageBox.critical") as mock_crit:
            self.window.prompt_drop_database("mysql")
            mock_crit.assert_called_once()
            self.assertIn("Protected System Database", mock_crit.call_args[0][1])

    def test_create_table_dialog_templates_and_ddl_generation(self) -> None:
        dialog = CreateTableDialog(self.window, target_db="test_db")
        # Test default Students template
        dialog.template_combo.setCurrentText("Students / School")
        self.assertEqual(dialog.name_edit.text(), "students")
        tbl, mysql_sql = dialog.get_create_table_sql("mysql")
        self.assertEqual(tbl, "students")
        self.assertIn("CREATE TABLE IF NOT EXISTS `test_db`.`students`", mysql_sql)
        self.assertIn("AUTO_INCREMENT", mysql_sql)
        self.assertIn("PRIMARY KEY (`student_id`)", mysql_sql)
        self.assertIn("ENGINE=InnoDB DEFAULT CHARSET=utf8mb4", mysql_sql)

        # Test SQLite DDL dialect
        dialog.template_combo.setCurrentText("Products / E-Commerce")
        self.assertEqual(dialog.name_edit.text(), "products")
        tbl_sq, sqlite_sql = dialog.get_create_table_sql("sqlite")
        self.assertEqual(tbl_sq, "products")
        self.assertIn("CREATE TABLE IF NOT EXISTS `products`", sqlite_sql)
        self.assertIn("INTEGER PRIMARY KEY AUTOINCREMENT", sqlite_sql)
        self.assertNotIn("ENGINE=InnoDB", sqlite_sql)

        # Test Employees / HR template
        dialog.template_combo.setCurrentText("Employees / HR")
        self.assertEqual(dialog.name_edit.text(), "employees")
        tbl_emp, emp_sql = dialog.get_create_table_sql("mysql")
        self.assertEqual(tbl_emp, "employees")
        self.assertIn("`department` VARCHAR(80)", emp_sql)
        self.assertIn("`salary` DECIMAL(10,2)", emp_sql)

        # Verify expanded template library size
        self.assertGreaterEqual(len(CreateTableDialog.TEMPLATES), 20)
        dialog.close()

    def test_prompt_create_table_execution(self) -> None:
        # Test prompt_create_table in SQLite mode
        with patch.object(CreateTableDialog, "exec", return_value=QDialog.DialogCode.Accepted):
            with patch.object(
                CreateTableDialog,
                "get_create_table_sql",
                return_value=("courses", "CREATE TABLE `courses` (id INTEGER PRIMARY KEY, title TEXT);"),
            ):
                self.window.prompt_create_table()
        self.assertIn("courses", self.manager.sqlite.get_schema())
        self.assertEqual(self.window.active_table_name, "courses")
        self.assertIn("Created table `courses` successfully", self.window.status_label.text())

    def test_schema_filter_tree(self) -> None:
        self.window.seed_demo_data()
        self.window.refresh_schema()
        # Filter for 'students'
        self.window.schema_search.setText("students")
        root = self.window.schema_tree.topLevelItem(0)
        self.assertFalse(root.isHidden())
        # Filter for non-existent table
        self.window.schema_search.setText("non_existent_table_xyz")
        self.assertTrue(root.isHidden())
        # Clear filter restores visibility
        self.window.schema_search.setText("")
        self.assertFalse(root.isHidden())


if __name__ == "__main__":
    unittest.main()
