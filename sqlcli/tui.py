"""Terminal User Interface (TUI) Studio for SQLCLI.
Spacious, full-screen terminal dashboard supporting SQL (MySQL), SQLite, and NoSQL.
"""

from __future__ import annotations

import csv
import difflib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    DynamicContainer,
    HSplit,
    Layout,
    VSplit,
    Window,
)
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea
from tabulate import tabulate

from .autopilot import generate_autopilot_plan
from .clipboard import get_clipboard_text, set_clipboard_text
from .config import Settings
from .connection import Database
from .diagnostics import SQLDiagnostic, analyze_error
from .knowledge import TOPICS, list_topics, lookup_topic
from .multi_engine import MultiEngineManager
from .queries import load_queries, save_query

TUI_STYLE = Style.from_dict({
    "header": "bg:#0F131C #38BDF8 bold",
    "footer": "bg:#161B26 #94A3B8",
    "frame.label": "#38BDF8 bold",
    "frame.border": "#283347",
    "frame.error.label": "#F43F5E bold",
    "frame.error.border": "#E11D48",
    "text-area": "bg:#07080C #F8FAFC",
    "text-area.prompt": "bg:#07080C #38BDF8 bold",
    "status.ok": "#10B981 bold",
    "status.err": "#F43F5E bold",
    "status.banner": "bg:#0F131C #94A3B8",
    "engine.active": "bg:#38BDF8 #090B10 bold",
    "tab": "bg:#161B26 #94A3B8",
    "tab.active": "bg:#38BDF8 #07080C bold",
    "line-number": "#475569",
    "line-number.current": "#38BDF8 bold",
    "scrollbar": "bg:#0F131C #38BDF8",
    "scrollbar.button": "bg:#38BDF8 #07080C",
    "scrollbar.arrow": "#38BDF8",
})


class TerminalStudio:
    """Spacious full-screen terminal workbench with tabbed sidebar, history, and diagnostics."""

    def __init__(
        self,
        engine_manager: MultiEngineManager,
        settings: Settings,
        mysql_db: Database,
        input: Any = None,
        output: Any = None,
    ) -> None:
        self.engine_manager = engine_manager
        self.settings = settings
        self.mysql = mysql_db

        # Default to local zero-setup SQLite engine
        self.engine_manager.active_engine = "sqlite"

        if output is None:
            try:
                from prompt_toolkit.output.defaults import create_output
                actual_output = create_output()
            except Exception:
                from prompt_toolkit.output import DummyOutput
                actual_output = DummyOutput()
        else:
            actual_output = output

        # State management
        self.last_diagnostic: SQLDiagnostic | None = None
        self.last_headers: list[str] | None = None
        self.last_rows: list[tuple] | None = None
        self.status_message = "Ready. Press [F3] to seed sample data, or type SQL and press [F5]."
        self.active_sidebar_tab: str = "schema"  # "schema", "history", "tutor"
        self.is_results_maximized: bool = False
        self._history_records: list[dict[str, Any]] = []

        # UI TextAreas — without hardcoded fixed heights so they flex to window size
        self.autopilot_area = TextArea(
            text="",
            multiline=False,
            wrap_lines=False,
            height=1,
            prompt="Goal > ",
        )

        self.editor_area = TextArea(
            text="-- Welcome to SQLCLI Terminal Studio!\n-- Press [F3] to seed demo data, or write queries below.\nSELECT 1 AS status, 'Studio Ready' AS message;\n",
            multiline=True,
            line_numbers=True,
            wrap_lines=False,
            scrollbar=True,
        )

        self.error_area = TextArea(
            text="✓ Diagnostics Clear. No errors detected.",
            multiline=True,
            read_only=True,
            wrap_lines=True,
            scrollbar=True,
        )

        self.results_area = TextArea(
            text="+----+--------+--------------+\n|    | status | message      |\n+====+========+==============+\n|  0 |      1 | Studio Ready |\n+----+--------+--------------+\n\n1 row(s) returned.",
            multiline=True,
            read_only=True,
            wrap_lines=False,
            scrollbar=True,
            focusable=True,
        )

        self.schema_area = TextArea(
            text="Loading tables...",
            multiline=True,
            read_only=True,
            wrap_lines=False,
            scrollbar=True,
            focusable=True,
        )

        self.history_area = TextArea(
            text="No previous work yet.\nExecuted queries appear here.",
            multiline=True,
            read_only=True,
            wrap_lines=False,
            scrollbar=True,
            focusable=True,
        )

        self.tutor_area = TextArea(
            text="[F7] Browse W3Schools Topics\n\n• SELECT (Query records)\n• WHERE (Filter data)\n• ORDER BY (Sorting)\n• JOINS (Inner, Left, Right)\n• GROUP BY (Aggregates)\n• CREATE TABLE (DDL)\n• CONSTRAINTS (PK, FK)",
            multiline=True,
            read_only=True,
            wrap_lines=True,
            scrollbar=True,
            focusable=True,
        )

        self._tutor_topic_index = 0
        self._all_topics = list_topics()

        # Build Layout & Application with mouse wheel and click support
        self.layout = self._create_layout()
        self.key_bindings = self._create_key_bindings()
        self.app = Application(
            layout=self.layout,
            key_bindings=self.key_bindings,
            style=TUI_STYLE,
            full_screen=True,
            mouse_support=True,
            enable_page_navigation_bindings=True,
            input=input,
            output=actual_output,
        )

        # Initial data load
        self.refresh_schema()
        self.refresh_history()

    def _header_text(self) -> list[tuple[str, str]]:
        eng = self.engine_manager.active_engine.upper()
        if eng == "SQLITE":
            target = f"SQLite ({self.engine_manager.sqlite.db_path.name})"
        elif eng == "MYSQL":
            target = f"MySQL ({self.settings.host}:{self.settings.port}/{self.settings.database or 'none'})"
        else:
            target = f"NoSQL ({self.engine_manager.nosql.db_path.name})"

        return [
            ("class:header", "  ⚡ SQLCLI TERMINAL STUDIO  "),
            ("class:header", "│ "),
            ("class:engine.active", f" Engine: [{eng}] "),
            ("class:header", f"  {target}  │ "),
            ("class:header", f"{self.status_message[:65]}  "),
        ]

    def _footer_text(self) -> list[tuple[str, str]]:
        return [
            ("class:footer", " [F1: Help] "),
            ("class:footer", "[F2: Engine] "),
            ("class:footer", "[F3: Seed Demo] "),
            ("class:footer", "[F4: Results] "),
            ("class:footer", "[F5: Run] "),
            ("class:footer", "[F6: Auto-Fix] "),
            ("class:footer", "[F7: Tutor] "),
            ("class:footer", "[F8: Autopilot] "),
            ("class:footer", "[F9: Export] "),
            ("class:footer", "[F11: Zoom] "),
            ("class:footer", "[1/2/3: Tabs] "),
            ("class:footer", "[F10: Quit] "),
        ]

    def _sidebar_tab_bar(self) -> list[tuple[str, str]]:
        active = self.active_sidebar_tab
        return [
            ("class:tab.active" if active == "schema" else "class:tab", " [1: Schema] "),
            ("class:tab.active" if active == "history" else "class:tab", " [2: History] "),
            ("class:tab.active" if active == "tutor" else "class:tab", " [3: Tutor] "),
            ("class:footer", "  Enter: Select/Load "),
        ]

    def _get_sidebar_content(self) -> Any:
        if self.active_sidebar_tab == "history":
            return Frame(
                self.history_area,
                title="🕒 Previous Work (Enter: Load Query · Arrows/Scroll)",
            )
        elif self.active_sidebar_tab == "tutor":
            return Frame(
                self.tutor_area,
                title="📚 SQL Tutor (Enter/F7: Load Example)",
            )
        return Frame(
            self.schema_area,
            title="📁 Tables & Schema (Enter on Table: SELECT Query)",
        )

    def _success_banner_text(self) -> list[tuple[str, str]]:
        eng = self.engine_manager.active_engine.upper()
        count_str = f" · {len(self.last_rows)} row(s)" if self.last_rows is not None else ""
        return [
            ("class:status.ok", "  ✓ Query OK "),
            ("class:status.banner", f"│ Engine: [{eng}]{count_str} │ [F5: Run]  [F6: Fix]  [F9: Export CSV]  [F11: Zoom Results] "),
        ]

    def _get_status_or_error_content(self) -> Any:
        if self.last_diagnostic:
            return Frame(
                self.error_area,
                title="🚨 Error Diagnostics HUD (Press [F6] to Auto-Fix  ·  Plain English Guide)",
                style="class:frame.error",
                height=Dimension(min=4, preferred=6, max=7),
            )
        return Window(
            content=FormattedTextControl(self._success_banner_text),
            height=1,
            style="class:status.banner",
        )

    def _get_right_column_content(self) -> Any:
        if self.is_results_maximized:
            return HSplit([
                Window(
                    content=FormattedTextControl(lambda: [
                        ("class:header", "  📊 RESULTS GRID (MAXIMIZED VIEW) — Press [F11] to Restore Normal View  ")
                    ]),
                    height=1,
                    style="class:header",
                ),
                Frame(
                    self.results_area,
                    title="Query Results Grid (F9: Export CSV/JSON · Mouse Wheel / PageUp / PageDown to Scroll)",
                ),
            ])

        return HSplit([
            Frame(
                self.autopilot_area,
                title="✈ Autopilot (Natural Language SQL — Type goal & press Enter to run)",
                height=3,
            ),
            Frame(
                self.editor_area,
                title="📝 Code Editor (F5: Run · Shift+Tab: Indent · Ctrl+V: Paste · Ctrl+B: Format)",
                height=Dimension(min=5, preferred=8, weight=1),
            ),
            DynamicContainer(self._get_status_or_error_content),
            Frame(
                self.results_area,
                title="📊 Query Results Grid (F9: Export · F11: Zoom · Mouse Wheel to Scroll)",
                height=Dimension(min=5, preferred=12, weight=2),
            ),
        ])

    def _create_layout(self) -> Layout:
        header_window = Window(
            content=FormattedTextControl(self._header_text),
            height=1,
            style="class:header",
        )

        footer_window = Window(
            content=FormattedTextControl(self._footer_text),
            height=1,
            style="class:footer",
        )

        # Left Column: Tab bar on top + dynamic full-height container
        left_column = HSplit([
            Window(content=FormattedTextControl(self._sidebar_tab_bar), height=1),
            DynamicContainer(self._get_sidebar_content),
        ], width=38)

        # Right Column: Flexible proportional workspace
        right_column = DynamicContainer(self._get_right_column_content)

        workspace_split = VSplit([
            left_column,
            right_column,
        ])

        root_container = HSplit([
            header_window,
            workspace_split,
            footer_window,
        ])

        return Layout(root_container, focused_element=self.editor_area)

    def switch_tab(self, tab: str) -> None:
        """Switch active sidebar tab (schema, history, tutor) and set focus."""
        self.active_sidebar_tab = tab
        if tab == "schema":
            self.refresh_schema()
            if hasattr(self, "app"):
                self.app.layout.focus(self.schema_area)
        elif tab == "history":
            self.refresh_history()
            if hasattr(self, "app"):
                self.app.layout.focus(self.history_area)
        elif tab == "tutor":
            if hasattr(self, "app"):
                self.app.layout.focus(self.tutor_area)
        self.status_message = f"Switched to {tab.upper()} tab. Press Enter to use selection."

    def toggle_maximize_results(self) -> None:
        """Toggle full-screen view for the Results Grid."""
        self.is_results_maximized = not self.is_results_maximized
        if self.is_results_maximized:
            self.status_message = "Maximized Results Grid. Press [F11] to restore editor."
            self.app.layout.focus(self.results_area)
        else:
            self.status_message = "Restored normal studio layout."
            self.app.layout.focus(self.editor_area)

    def seed_demo_data(self) -> None:
        """Seed clean sample tables (students & courses) into the active engine."""
        self.engine_manager.load_sample_data(self.engine_manager.active_engine)
        self.status_message = "Sample tables 'students' and 'courses' seeded!"
        if self.engine_manager.active_engine == "nosql":
            self.editor_area.text = "db.students.find();\n"
        else:
            self.editor_area.text = "SELECT id, name, major, gpa FROM students ORDER BY gpa DESC;\n"
        self.refresh_schema()
        self.run_current_query()

    def load_selected_history_item(self) -> None:
        """Load query from history row at cursor into the Code Editor."""
        if not self._history_records:
            self.status_message = "History is empty."
            return
        row = self.history_area.document.cursor_position_row
        if 0 <= row < len(self._history_records):
            rec = self._history_records[row]
            query = rec.get("query", "").strip()
            if query:
                self.editor_area.text = query + ("\n" if not query.endswith("\n") else "")
                self.status_message = f"✓ Loaded query #{row + 1} from history into editor. Press [F5] to run."
                self.app.layout.focus(self.editor_area)

    def load_selected_schema_table(self) -> None:
        """Generate SELECT query for the table under cursor in schema area."""
        line = self.schema_area.document.current_line.strip()
        match = re.search(r"•\s*([`\w$]+)", line)
        if match:
            tbl = match.group(1)
            eng = self.engine_manager.active_engine
            if eng == "nosql":
                self.editor_area.text = f"db.{tbl}.find();\n"
            else:
                self.editor_area.text = f"SELECT * FROM {tbl} LIMIT 50;\n"
            self.status_message = f"✓ Generated query for '{tbl}'. Press [F5] to run."
            self.app.layout.focus(self.editor_area)
        else:
            self.status_message = "Move cursor to a table line (marked with •) and press Enter."

    def load_selected_tutor_example(self) -> None:
        """Load example query of current W3Schools topic into editor."""
        if not self._all_topics:
            return
        idx = max(0, self._tutor_topic_index - 1) % len(self._all_topics)
        topic_name = self._all_topics[idx]
        topic = lookup_topic(topic_name)
        if topic and topic.example:
            self.editor_area.text = topic.example.strip() + "\n"
            self.status_message = f"✓ Loaded example for '{topic.name}'. Press [F5] to run."
            self.app.layout.focus(self.editor_area)

    def format_editor_sql(self) -> None:
        """Format and uppercase standard SQL keywords in Code Editor."""
        sql = self.editor_area.text
        if not sql.strip():
            return
        keywords = [
            "CREATE TABLE IF NOT EXISTS", "CREATE TABLE", "CREATE DATABASE IF NOT EXISTS", "CREATE DATABASE",
            "DROP TABLE IF EXISTS", "DROP TABLE", "DROP DATABASE IF EXISTS", "DROP DATABASE",
            "ALTER TABLE", "ADD COLUMN", "INSERT INTO", "VALUES", "UPDATE", "SET", "DELETE FROM", "DELETE",
            "SELECT DISTINCT", "SELECT", "FROM", "WHERE", "GROUP BY", "ORDER BY", "HAVING", "LIMIT",
            "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN", "JOIN", "ON",
            "PRIMARY KEY", "FOREIGN KEY", "REFERENCES", "AUTO_INCREMENT", "AUTOINCREMENT",
            "DEFAULT", "CHECK", "UNIQUE", "NOT NULL", "NULL", "AND", "OR", "NOT", "IN", "BETWEEN", "LIKE", "IS",
        ]
        formatted = sql
        for kw in keywords:
            formatted = re.sub(r"\b" + re.escape(kw) + r"\b", kw, formatted, flags=re.IGNORECASE)
        self.editor_area.text = formatted
        self.status_message = "✓ Formatted SQL keywords in editor."

    def _create_key_bindings(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("f10")
        @kb.add("c-q")
        def _exit(event):
            event.app.exit()

        @kb.add("f1")
        def _help(event):
            self.show_help()

        @kb.add("f2")
        def _cycle_engine(event):
            engines = ["sqlite", "mysql", "nosql"]
            idx = (engines.index(self.engine_manager.active_engine) + 1) % len(engines)
            self.engine_manager.active_engine = engines[idx]
            self.status_message = f"Switched active engine to {engines[idx].upper()}."
            self.refresh_schema()

        @kb.add("f3")
        def _seed_demo(event):
            self.seed_demo_data()

        @kb.add("f4")
        def _toggle_focus_results(event):
            if event.app.layout.has_focus(self.results_area):
                event.app.layout.focus(self.editor_area)
            else:
                event.app.layout.focus(self.results_area)

        @kb.add("f5")
        @kb.add("escape", "enter")
        def _run_query(event):
            self.run_current_query()

        @kb.add("f6")
        def _auto_fix(event):
            self.apply_auto_fix()

        @kb.add("f7")
        def _tutor_next(event):
            self.switch_tab("tutor")
            self.cycle_tutor_topic()

        @kb.add("f8")
        def _focus_autopilot(event):
            event.app.layout.focus(self.autopilot_area)

        @kb.add("f9")
        def _save_query(event):
            self.save_results_dialog()

        @kb.add("f11")
        @kb.add("c-m")
        def _toggle_zoom(event):
            self.toggle_maximize_results()

        @kb.add("c-b")
        def _format_sql(event):
            self.format_editor_sql()

        @kb.add("c-l")
        def _clear_editor(event):
            if event.app.layout.has_focus(self.editor_area):
                self.editor_area.text = ""
                self.status_message = "Cleared Code Editor."

        # Quick tab switching: 1 for Schema, 2 for History, 3 for Tutor
        @kb.add("1")
        def _tab_1(event):
            if event.app.layout.has_focus(self.editor_area):
                self.editor_area.buffer.insert_text("1")
            elif event.app.layout.has_focus(self.autopilot_area):
                self.autopilot_area.buffer.insert_text("1")
            else:
                self.switch_tab("schema")

        @kb.add("2")
        def _tab_2(event):
            if event.app.layout.has_focus(self.editor_area):
                self.editor_area.buffer.insert_text("2")
            elif event.app.layout.has_focus(self.autopilot_area):
                self.autopilot_area.buffer.insert_text("2")
            else:
                self.switch_tab("history")

        @kb.add("3")
        def _tab_3(event):
            if event.app.layout.has_focus(self.editor_area):
                self.editor_area.buffer.insert_text("3")
            elif event.app.layout.has_focus(self.autopilot_area):
                self.autopilot_area.buffer.insert_text("3")
            else:
                self.switch_tab("tutor")

        # Shift+Tab indentation in editor
        @kb.add("s-tab")
        def _shift_tab(event):
            if event.app.layout.has_focus(self.editor_area):
                self.editor_area.buffer.insert_text("    ")
            elif event.app.layout.has_focus(self.results_area):
                event.app.layout.focus(self.editor_area)
            elif event.app.layout.has_focus(self.schema_area) or event.app.layout.has_focus(self.history_area) or event.app.layout.has_focus(self.tutor_area):
                event.app.layout.focus(self.results_area)

        # Ctrl+V paste clipboard in editor
        @kb.add("c-v")
        def _paste(event):
            clip = get_clipboard_text()
            if clip and event.app.layout.has_focus(self.editor_area):
                self.editor_area.buffer.insert_text(clip)

        # Tab key cycles panel focus through Editor -> Results -> Sidebar -> Autopilot
        @kb.add("tab")
        def _next_panel(event):
            if event.app.layout.has_focus(self.autopilot_area):
                event.app.layout.focus(self.editor_area)
            elif event.app.layout.has_focus(self.editor_area):
                event.app.layout.focus(self.results_area)
            elif event.app.layout.has_focus(self.results_area):
                if self.active_sidebar_tab == "history":
                    event.app.layout.focus(self.history_area)
                elif self.active_sidebar_tab == "tutor":
                    event.app.layout.focus(self.tutor_area)
                else:
                    event.app.layout.focus(self.schema_area)
            else:
                event.app.layout.focus(self.autopilot_area)

        # Enter key behavior depends on focused panel
        @kb.add("enter")
        def _smart_enter(event):
            if event.app.layout.has_focus(self.autopilot_area):
                goal = self.autopilot_area.text.strip()
                if goal:
                    sql, cat, exp = generate_autopilot_plan(
                        goal,
                        self.mysql if self.engine_manager.active_engine == "mysql" else None,
                        self.settings,
                    )
                    self.editor_area.text = sql + "\n"
                    self.autopilot_area.text = ""
                    event.app.layout.focus(self.editor_area)
                    self.status_message = f"Autopilot synthesized: {cat}"
                    self.run_current_query()
            elif event.app.layout.has_focus(self.history_area):
                self.load_selected_history_item()
            elif event.app.layout.has_focus(self.schema_area):
                self.load_selected_schema_table()
            elif event.app.layout.has_focus(self.tutor_area):
                self.load_selected_tutor_example()
            elif event.app.layout.has_focus(self.editor_area):
                self.editor_area.buffer.insert_text("\n")

        return kb

    def refresh_schema(self) -> None:
        """Update schema tree in left panel."""
        eng = self.engine_manager.active_engine
        schema = self.engine_manager.get_schema(eng)
        if not schema:
            self.schema_area.text = (
                f"No tables found in {eng.upper()}.\n\n"
                "• Press [F3] to Seed Demo Data\n"
                "• Or write: CREATE TABLE ..."
            )
            return

        lines = [
            f"DATABASE: {eng.upper()} ({len(schema)} table(s))\n",
            "Tip: Press Enter on any table (•) to generate SELECT query.\n",
        ]
        for tbl, cols in schema.items():
            lines.append(f"• {tbl} ({len(cols)} columns)")
            for col in cols[:8]:
                lines.append(f"   ├── {col}")
            if len(cols) > 8:
                lines.append(f"   └── ... ({len(cols) - 8} more columns)")
            lines.append("")
        self.schema_area.text = "\n".join(lines)

    def refresh_history(self) -> None:
        """Update previous work list in left panel."""
        records = self.engine_manager.load_history(30)
        self._history_records = list(reversed(records[-30:]))
        if not self._history_records:
            self.history_area.text = "No history recorded yet.\nRun queries to see past work here."
            return

        lines = ["Tip: Press Enter on any query to load into Editor.\n"]
        for i, rec in enumerate(self._history_records, 1):
            st = "OK " if rec.get("status") == "SUCCESS" else "ERR"
            ms = f"{rec.get('elapsed_ms', 0):.1f}ms"
            query = " ".join(rec.get("query", "").split())[:32]
            lines.append(f"[{st}] {ms:>6}  {query}")
        self.history_area.text = "\n".join(lines)

    def cycle_tutor_topic(self) -> None:
        """Cycle through W3Schools topics and load card into tutor area and editor."""
        if not self._all_topics:
            return
        topic_name = self._all_topics[self._tutor_topic_index % len(self._all_topics)]
        self._tutor_topic_index += 1
        topic = lookup_topic(topic_name)
        if topic:
            self.tutor_area.text = (
                f"Topic: {topic.name} ({topic.category})\n"
                f"Tip: Press Enter or F7 to load example into editor.\n\n"
                f"SYNTAX:\n{topic.syntax}\n\n"
                f"SUMMARY:\n{topic.summary}\n\n"
                f"EXAMPLE:\n{topic.example}"
            )
            self.editor_area.text = topic.example + "\n"
            self.status_message = f"Loaded tutorial example for '{topic.name}'. Press [F5] to run."

    def run_current_query(self) -> None:
        """Execute the query currently written in the Code Editor."""
        query = self.editor_area.text.strip()
        if not query:
            self.status_message = "Editor is empty. Type a query first."
            return

        eng = self.engine_manager.active_engine
        headers, rows, count, elapsed_ms, err = self.engine_manager.execute(query, eng)

        if err:
            # Triangulate diagnostic with full schema context
            schema = self.engine_manager.get_schema(eng)
            diag = analyze_error(query, err, schema, engine=eng)
            self.last_diagnostic = diag

            # Render spacious, beginner-friendly Error HUD
            err_lines = [
                f"✖ PROBLEM: {diag.error_type} — {diag.plain_summary or diag.explanation} (Line {diag.line_number})",
                f"  Why it failed: {diag.why_failed or diag.explanation}",
                f"  Rule to learn: {diag.rule_tip or 'Check syntax against W3Schools Guide [F7]'}",
                f"  Suggested fix: {diag.suggested_fix}",
            ]
            if diag.corrected_sql:
                one_line = diag.corrected_sql.strip().replace("\n", " ")[:60]
                err_lines.append(f"  ⚡ AUTO-FIX  : [Press F6 to apply '{one_line}']")

            self.error_area.text = "\n".join(err_lines)
            self.status_message = f"Error: {diag.plain_summary[:45]} (Press [F6] to fix)"
        else:
            self.last_diagnostic = None
            self.error_area.text = f"✓ Query OK. Executed cleanly in {elapsed_ms:.2f}ms on [{eng.upper()}]."

            if headers and rows is not None:
                self.last_headers = headers
                self.last_rows = rows
                grid = tabulate(rows, headers=headers, tablefmt="grid", showindex=True)
                summary = f"\n\n✓ {len(rows)} row(s) returned in {elapsed_ms:.2f}ms [{eng.upper()}]."
                self.results_area.text = grid + summary
                self.status_message = f"Query OK. Displaying {len(rows)} row(s)."
            else:
                self.results_area.text = (
                    f"+---------------------------------------------------------+\n"
                    f"| Statement executed successfully in {elapsed_ms:.2f}ms.          |\n"
                    f"| Rows affected: {count:<40} |\n"
                    f"| Engine: {eng.upper():<47} |\n"
                    f"+---------------------------------------------------------+"
                )
                self.status_message = f"Statement executed successfully ({count} affected)."

        self.refresh_history()
        self.refresh_schema()

    def apply_auto_fix(self) -> None:
        """Apply suggested fix from Error HUD into editor and re-execute."""
        if not self.last_diagnostic:
            self.status_message = "No active error to fix."
            return

        diag = self.last_diagnostic
        # 1. Deterministic corrected query
        if diag.corrected_sql:
            self.editor_area.text = diag.corrected_sql
            self.status_message = "✓ Applied auto-fix! Re-running query..."
            self.run_current_query()
            return

        if not diag.suggested_fix:
            self.status_message = "No automated patch available for this error."
            return

        sql = self.editor_area.text

        # 2. Typo replacement
        match = re.search(r"replace '([^']+)' with '([^']+)'", diag.suggested_fix, re.IGNORECASE)
        if match:
            old_tok, new_tok = match.group(1), match.group(2)
            sql = re.sub(r"\b" + re.escape(old_tok) + r"\b", new_tok, sql, flags=re.IGNORECASE)
            self.editor_area.text = sql
            self.status_message = f"Replaced '{old_tok}' with '{new_tok}'. Re-running query..."
            self.run_current_query()
            return

        # 3. Table name suggestion
        match_table = re.search(r"to '([^']+)'", diag.suggested_fix)
        if match_table and diag.faulty_snippet:
            new_table = match_table.group(1)
            sql = sql.replace(diag.faulty_snippet, new_table)
            self.editor_area.text = sql
            self.status_message = f"Corrected table to '{new_table}'. Re-running query..."
            self.run_current_query()
            return

    def show_help(self) -> None:
        """Display help overview inside Results area."""
        self.results_area.text = """
================================================================================
                    SQLCLI TERMINAL STUDIO — KEYBOARD GUIDE
================================================================================

  NAVIGATION & TABS:
    [1]         Tab 1        : Switch sidebar to Tables & Schema Explorer
    [2]         Tab 2        : Switch sidebar to Previous Work (History)
    [3]         Tab 3        : Switch sidebar to W3Schools SQL Tutor
    [Tab]       Cycle Focus  : Move focus between Editor, Results, Sidebar, Autopilot
    [F4]        Toggle View  : Toggle focus between Code Editor and Results Grid
    [F11]/^M    Zoom Results : Maximize Results Grid full screen (toggle back anytime)
    Mouse Wheel Scroll       : Scroll any panel or result table smoothly

  QUERY EXECUTION & CODE:
    [F5] / Enter: Run        : Execute current SQL / NoSQL in Code Editor
    [F6]        Auto-Fix     : Automatically apply diagnosed fix and re-run query
    [F3]        Seed Demo    : Populate sample 'students' and 'courses' database
    [F2]        Engine       : Switch between SQLite, MySQL (XAMPP), and NoSQL
    [F8]        Autopilot    : Jump to Autopilot bar to synthesize SQL in plain English
    [F9]        Export Data  : Export query results to CSV and JSON on disk
    [Ctrl+B]    Format SQL   : Uppercase keywords and format query
    [Ctrl+L]    Clear Editor : Erase editor text
    [Shift+Tab] Indent       : Insert 4 spaces in Code Editor anytime
    [Ctrl+V]    Paste        : Paste clipboard text at cursor into Code Editor

  SIDEBAR ACTIONS (Press Enter on selection):
    In Schema   [Enter]      : Generates 'SELECT * FROM table LIMIT 50;' in Editor
    In History  [Enter]      : Loads highlighted previous query back into Editor
    In Tutor    [Enter] / F7 : Loads W3Schools working example query into Editor
================================================================================
"""

    def save_results_dialog(self) -> None:
        """Save current query and export result rows to results.csv and results.json."""
        sql = self.editor_area.text.strip()
        if sql:
            name = f"query_{int(time.time())}"
            save_query(name, sql)

        if not self.last_headers or not self.last_rows:
            self.status_message = "No result rows to export. Run a query that returns data first."
            return

        csv_file = Path("results.csv")
        try:
            with csv_file.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.last_headers)
                writer.writerows(self.last_rows)

            json_file = Path("results.json")
            json_data = [dict(zip(self.last_headers, row)) for row in self.last_rows]
            json_file.write_text(json.dumps(json_data, indent=2, default=str), encoding="utf-8")

            self.status_message = f"✓ Exported {len(self.last_rows)} row(s) to results.csv and results.json!"
        except Exception as exc:
            self.status_message = f"Export failed: {exc}"

    def save_query_dialog(self) -> None:
        """Save current query into saved queries store."""
        sql = self.editor_area.text.strip()
        if not sql:
            self.status_message = "Cannot save empty editor."
            return
        name = f"query_{int(time.time())}"
        save_query(name, sql)
        self.status_message = f"Saved current query as '{name}'."

    def run(self) -> None:
        """Launch the Terminal Studio application."""
        self.app.run()

    def close(self) -> None:
        """Release multi-engine connections and clean up."""
        self.engine_manager.close()


def start_terminal_studio(engine_manager: MultiEngineManager, settings: Settings, mysql_db: Database) -> None:
    """Entry point to launch the Terminal Studio."""
    studio = TerminalStudio(engine_manager, settings, mysql_db)
    studio.run()
