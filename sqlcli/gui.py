"""Native PyQt6 Desktop Studio for SQLCLI.
Standalone, high-performance database workbench supporting SQLite, MySQL, and NoSQL.
TablePlus-style data-first architecture with instant spreadsheet inspection, direct
record adding/editing/deleting, real-time sync, and SQL query console.
"""

from __future__ import annotations

import csv
import json
import os
import re
import socket
import sys
import time
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QPoint, QRect, QSize, QStringListModel, Qt, QTimer
from PyQt6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .autopilot import generate_autopilot_plan
from .config import Settings
from .connection import Database
from .diagnostics import SQLDiagnostic, analyze_error
from .knowledge import (
    TOPICS,
    adapt_query_to_schema,
    filter_topics,
    get_categories,
    get_topic_challenge,
    list_topics,
    lookup_topic,
)
from .multi_engine import MultiEngineManager
from .queries import save_query

def _get_check_icon_path() -> str:
    """Generate and return POSIX path to check.png icon."""
    assets_dir = Path(__file__).parent / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    check_file = assets_dir / "check.png"
    if not check_file.exists():
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#FFFFFF"))
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawLine(3, 8, 7, 12)
        p.drawLine(7, 12, 13, 4)
        p.end()
        pix.save(str(check_file))
    return check_file.resolve().as_posix()


CHECK_ICON_URL = _get_check_icon_path()

OBSIDIAN_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #07080C;
    color: #F8FAFC;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    font-size: 9.5pt;
}
QToolBar {
    background-color: #0B0E17;
    border-bottom: 1px solid #1E293B;
    spacing: 6px;
    padding: 6px 12px;
}
QToolButton, QPushButton {
    background-color: #121824;
    color: #E2E8F0;
    border: 1px solid #222E42;
    border-radius: 6px;
    padding: 5px 12px;
    font-weight: 600;
    font-size: 9pt;
}
QToolButton:hover, QPushButton:hover {
    background-color: #1A2333;
    border-color: #38BDF8;
    color: #38BDF8;
}
QPushButton#primaryBtn {
    background-color: #059669;
    color: #FFFFFF;
    border: 1px solid #10B981;
    font-weight: bold;
}
QPushButton#primaryBtn:hover {
    background-color: #047857;
    border-color: #34D399;
}
QPushButton#addBtn {
    background-color: #064E3B;
    color: #6EE7B7;
    border: 1px solid #059669;
    font-weight: bold;
}
QPushButton#addBtn:hover {
    background-color: #065F46;
    color: #FFFFFF;
    border-color: #10B981;
}
QPushButton#deleteBtn {
    background-color: #4C0519;
    color: #FDA4AF;
    border: 1px solid #9F1239;
    font-weight: bold;
}
QPushButton#deleteBtn:hover {
    background-color: #881337;
    border-color: #F43F5E;
    color: #FFFFFF;
}
QPushButton#modeActiveBtn {
    background-color: #0284C7;
    color: #FFFFFF;
    border: 1px solid #38BDF8;
    font-weight: bold;
}
QPushButton#modeInactiveBtn {
    background-color: #0D111A;
    color: #94A3B8;
    border: 1px solid #1E2535;
}
QPushButton#modeInactiveBtn:hover {
    background-color: #172030;
    color: #F8FAFC;
    border-color: #38BDF8;
}
QPushButton#fixBtn {
    background-color: #1E3A8A;
    color: #93C5FD;
    border: 1px solid #3B82F6;
    font-weight: bold;
}
QPushButton#fixBtn:hover {
    background-color: #1D4ED8;
    color: #FFFFFF;
    border-color: #60A5FA;
}
QPushButton.chipBtn {
    background-color: #0F1420;
    color: #94A3B8;
    border: 1px solid #1E293B;
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 8.5pt;
    font-weight: 500;
}
QPushButton.chipBtn:hover {
    background-color: #1A2438;
    border-color: #38BDF8;
    color: #38BDF8;
}
QComboBox, QLineEdit {
    background-color: #0B0F19;
    color: #F8FAFC;
    border: 1px solid #222E44;
    border-radius: 6px;
    padding: 5px 9px;
    selection-background-color: #0284C7;
    font-size: 9.5pt;
}
QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #38BDF8;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
    padding-right: 4px;
}
QComboBox QAbstractItemView {
    background-color: #0C101B;
    color: #F8FAFC;
    border: 1px solid #2A3B57;
    border-radius: 6px;
    padding: 4px;
    selection-background-color: #1A2840;
    selection-color: #38BDF8;
    outline: none;
}
QComboBox QAbstractItemView::item {
    min-height: 26px;
    padding: 4px 8px;
    border-radius: 4px;
}
QComboBox QAbstractItemView::item:selected, QComboBox QAbstractItemView::item:hover {
    background-color: #1A2840;
    color: #38BDF8;
    font-weight: 600;
}
QTabWidget::pane {
    border: 1px solid #1A2333;
    background-color: #0A0D15;
    border-radius: 6px;
}
QTabBar::tab {
    background-color: #0E121B;
    color: #94A3B8;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 3px;
    font-weight: 600;
    font-size: 9pt;
}
QTabBar::tab:selected {
    background-color: #0A0D15;
    color: #38BDF8;
    border-bottom: 2px solid #38BDF8;
}
QTabBar::tab:hover:!selected {
    background-color: #141B29;
    color: #F8FAFC;
}
QTreeWidget, QListWidget, QTableWidget, QPlainTextEdit {
    background-color: #07090F;
    color: #F8FAFC;
    border: 1px solid #1A2333;
    border-radius: 6px;
    gridline-color: #141B28;
    selection-background-color: #132742;
    selection-color: #38BDF8;
}
QTableWidget {
    font-variant-numeric: tabular-nums;
}
QTableWidget::item {
    padding: 4px 8px;
}
QTableWidget QLineEdit, QTableWidget QComboBox {
    background-color: #0E1320;
    color: #F8FAFC;
    border: 1px solid #223047;
    border-radius: 5px;
    padding: 3px 8px;
    min-height: 28px;
    font-size: 9.5pt;
}
QTableWidget QLineEdit:focus, QTableWidget QComboBox:focus {
    border: 1px solid #38BDF8;
}
QHeaderView::section {
    background-color: #0C101B;
    color: #94A3B8;
    padding: 7px 10px;
    border: none;
    border-right: 1px solid #1A2333;
    border-bottom: 1px solid #1A2333;
    font-weight: 700;
    font-size: 8.5pt;
    text-transform: uppercase;
}
QCheckBox {
    color: #F8FAFC;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #2B3A52;
    border-radius: 4px;
    background-color: #0B0F19;
}
QCheckBox::indicator:hover {
    border-color: #38BDF8;
}
QCheckBox::indicator:checked {
    background-color: #0284C7;
    border: 1px solid #38BDF8;
    image: url("__CHECK_ICON__");
}
QScrollBar:vertical {
    background-color: #07090E;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: #1A2333;
    min-height: 24px;
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background-color: #38BDF8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background-color: #07090E;
    height: 10px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background-color: #1A2333;
    min-width: 24px;
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #38BDF8;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QSplitter::handle {
    background-color: #121824;
}
QSplitter::handle:hover {
    background-color: #38BDF8;
}
QStatusBar {
    background-color: #090C14;
    color: #94A3B8;
    border-top: 1px solid #1A2333;
    font-size: 9pt;
}
QMenu {
    background-color: #0C101B;
    color: #F8FAFC;
    border: 1px solid #222E42;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 18px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #1A2840;
    color: #38BDF8;
}
QDialog {
    background-color: #090C14;
    color: #F8FAFC;
    border: 1px solid #222E42;
    border-radius: 8px;
}
QListView#completerPopup, QCompleter QAbstractItemView {
    background-color: #0C101B;
    color: #F8FAFC;
    border: 1px solid #38BDF8;
    border-radius: 6px;
    padding: 4px;
    selection-background-color: #1A2840;
    selection-color: #38BDF8;
    font-family: 'JetBrains Mono', 'Cascadia Code', monospace;
    font-size: 9.5pt;
    outline: none;
}
QListView#completerPopup::item, QCompleter QAbstractItemView::item {
    padding: 5px 8px;
    border-radius: 4px;
    min-height: 22px;
}
QListView#completerPopup::item:selected, QListView#completerPopup::item:hover,
QCompleter QAbstractItemView::item:selected, QCompleter QAbstractItemView::item:hover {
    background-color: #1A2840;
    color: #38BDF8;
    font-weight: bold;
}
""".replace("__CHECK_ICON__", CHECK_ICON_URL)


class SQLSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for SQL keywords, types, numbers, strings, and comments."""

    def __init__(self, parent: QTextDocument) -> None:
        super().__init__(parent)
        self.rules: list[tuple[re.Pattern, QTextCharFormat]] = []

        # Keywords (Sky Blue / Cyan)
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#38BDF8"))
        kw_fmt.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "SELECT", "FROM", "WHERE", "GROUP", "BY", "ORDER", "HAVING", "LIMIT", "OFFSET",
            "INSERT", "INTO", "VALUES", "UPDATE", "SET", "DELETE", "DROP", "CREATE", "ALTER",
            "TABLE", "DATABASE", "INDEX", "VIEW", "IF", "EXISTS", "NOT", "NULL", "PRIMARY",
            "KEY", "FOREIGN", "REFERENCES", "CHECK", "DEFAULT", "UNIQUE", "AUTO_INCREMENT",
            "AUTOINCREMENT", "JOIN", "INNER", "LEFT", "RIGHT", "FULL", "OUTER", "CROSS", "ON",
            "UNION", "ALL", "DISTINCT", "AS", "AND", "OR", "IN", "IS", "BETWEEN", "LIKE",
            "CASE", "WHEN", "THEN", "ELSE", "END", "ASC", "DESC", "TRUE", "FALSE", "PRAGMA",
            "DESCRIBE", "SHOW", "USE",
        ]
        for kw in keywords:
            pattern = re.compile(r"\b" + kw + r"\b", re.IGNORECASE)
            self.rules.append((pattern, kw_fmt))

        # Functions (Purple / Violet)
        fn_fmt = QTextCharFormat()
        fn_fmt.setForeground(QColor("#C084FC"))
        fn_fmt.setFontWeight(QFont.Weight.Bold)
        funcs = [
            "COUNT", "SUM", "AVG", "MIN", "MAX", "COALESCE", "ROUND", "UPPER", "LOWER",
            "CONCAT", "SUBSTR", "NOW", "LENGTH", "TRIM", "REPLACE",
        ]
        for fn in funcs:
            pattern = re.compile(r"\b" + fn + r"(?=\s*\()", re.IGNORECASE)
            self.rules.append((pattern, fn_fmt))

        # Data types (Teal / Emerald)
        type_fmt = QTextCharFormat()
        type_fmt.setForeground(QColor("#34D399"))
        types = [
            "INT", "INTEGER", "VARCHAR", "TEXT", "CHAR", "BOOLEAN", "FLOAT", "DOUBLE",
            "DECIMAL", "DATE", "DATETIME", "TIMESTAMP", "BLOB", "JSON",
        ]
        for tp in types:
            pattern = re.compile(r"\b" + tp + r"\b", re.IGNORECASE)
            self.rules.append((pattern, type_fmt))

        # Numbers (Orange / Amber)
        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#FB923C"))
        self.rules.append((re.compile(r"\b[0-9]+(?:\.[0-9]+)?\b"), num_fmt))

        # Strings (Yellow)
        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#FDE047"))
        self.rules.append((re.compile(r"'[^'\\]*(?:\\.[^'\\]*)*'"), str_fmt))
        self.rules.append((re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"'), str_fmt))

        # Comments (Slate Gray)
        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#64748B"))
        comment_fmt.setFontItalic(True)
        self.rules.append((re.compile(r"--[^\n]*"), comment_fmt))

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)


class LineNumberArea(QWidget):
    """Gutter widget that renders line numbers for the code editor."""

    def __init__(self, editor: CodeEditor) -> None:
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event: Any) -> None:
        self.code_editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    """Full-featured code editor with syntax highlighting, line numbers, and hotkeys."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)

        font = QFont("JetBrains Mono", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)
        self.highlight_current_line()
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.highlighter = SQLSyntaxHighlighter(self.document())
        self.completer: QCompleter | None = None
        self.on_run_requested: Any = None

    def set_completer(self, completer: QCompleter) -> None:
        if self.completer:
            try:
                self.completer.activated.disconnect()
            except Exception:
                pass
        self.completer = completer
        if not self.completer:
            return
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        popup = self.completer.popup()
        if popup:
            popup.setObjectName("completerPopup")
        self.completer.activated.connect(self._insert_completion)

    def _insert_completion(self, completion: str) -> None:
        tc = self.textCursor()
        prefix = self.text_under_cursor()
        if "." in prefix:
            last_dot = prefix.rfind(".")
            sub_prefix = prefix[last_dot + 1:]
            tc.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(sub_prefix))
            if completion.startswith(prefix[:last_dot + 1]):
                completion = completion[last_dot + 1:]
            tc.insertText(completion)
        else:
            tc.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(prefix))
            tc.insertText(completion)
        self.setTextCursor(tc)

    def text_under_cursor(self) -> str:
        tc = self.textCursor()
        block_text = tc.block().text()
        col = tc.positionInBlock()
        match = re.search(r"[\w$]+(?:\.[\w$]*)*$", block_text[:col])
        if match:
            return match.group(0)
        return ""

    def line_number_area_width(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        return 20 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_line_number_area_width(self, _: int) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def highlight_current_line(self) -> None:
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor("#121622")
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    def line_number_area_paint_event(self, event: Any) -> None:
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#090B10"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#475569"))
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 8,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def keyPressEvent(self, event: Any) -> None:
        # Check if user pressed Ctrl+Space to manually invoke suggestions
        is_ctrl_space = (
            event.key() == Qt.Key.Key_Space
            and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        )

        if self.completer and self.completer.popup() and self.completer.popup().isVisible():
            if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Tab):
                popup = self.completer.popup()
                current_idx = popup.currentIndex()
                if not current_idx.isValid():
                    current_idx = self.completer.completionModel().index(0, 0)
                if current_idx.isValid():
                    completion = current_idx.data()
                    self._insert_completion(completion)
                    popup.hide()
                    event.accept()
                    return
            elif event.key() == Qt.Key.Key_Escape:
                self.completer.popup().hide()
                event.accept()
                return
            elif event.key() in (Qt.Key.Key_Backtab,):
                event.ignore()
                return

        # F5 or Ctrl+Enter: run query
        if event.key() == Qt.Key.Key_F5 or (
            event.key() == Qt.Key.Key_Return
            and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        ):
            if self.on_run_requested:
                self.on_run_requested()
                return

        # Shift+Tab or Tab: insert 4 spaces when completion popup is not active
        if event.key() in (Qt.Key.Key_Backtab, Qt.Key.Key_Tab):
            self.textCursor().insertText("    ")
            return

        if not is_ctrl_space:
            super().keyPressEvent(event)

        # Autocomplete popup logic
        if self.completer:
            prefix = self.text_under_cursor()
            if is_ctrl_space or (len(prefix) >= 1 and not prefix.isnumeric()):
                if "." in prefix:
                    parts = prefix.split(".")
                    tbl = parts[0].strip("`")
                    sub_prefix = parts[1] if len(parts) > 1 else ""
                    if hasattr(self, "schema_columns") and tbl in self.schema_columns:
                        cols = self.schema_columns[tbl]
                        self.completer.model().setStringList(cols)
                        self.completer.setCompletionPrefix(sub_prefix)
                    else:
                        if hasattr(self, "all_words"):
                            self.completer.model().setStringList(self.all_words)
                        self.completer.setCompletionPrefix(sub_prefix or prefix)
                else:
                    if hasattr(self, "all_words"):
                        self.completer.model().setStringList(self.all_words)
                    self.completer.setCompletionPrefix(prefix)

                cr = self.cursorRect()
                popup = self.completer.popup()
                if self.completer.completionCount() > 0 or is_ctrl_space:
                    cr.setWidth(max(240, popup.sizeHintForColumn(0) + popup.verticalScrollBar().sizeHint().width() + 40))
                    self.completer.complete(cr)
                    first_idx = self.completer.completionModel().index(0, 0)
                    if first_idx.isValid():
                        popup.setCurrentIndex(first_idx)
                else:
                    popup.hide()
            else:
                if self.completer.popup():
                    self.completer.popup().hide()


class AddRecordDialog(QDialog):
    """Clean form modal to insert a new record into a table without writing SQL."""

    def __init__(
        self,
        parent: QWidget,
        table_name: str,
        columns_info: list[dict[str, Any]],
        engine_type: str,
    ) -> None:
        super().__init__(parent)
        self.table_name = table_name
        self.columns_info = columns_info
        self.engine_type = engine_type
        self.field_inputs: dict[str, QLineEdit] = {}

        self.setWindowTitle(f"Add Record · {table_name}")
        self.setMinimumWidth(480)
        self.setWindowModality(Qt.WindowModality.WindowModal)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header = QLabel(f"<b>Add New Record into <code>{table_name}</code></b>")
        header.setStyleSheet("font-size: 11pt; color: #38BDF8;")
        layout.addWidget(header)

        sub_info = QLabel("Fill column values below. Auto-increment primary keys are managed automatically.")
        sub_info.setStyleSheet("color: #94A3B8; font-size: 9pt;")
        layout.addWidget(sub_info)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        for col in columns_info:
            col_name = col["name"]
            col_type = col.get("type", "TEXT").upper()
            is_pk = col.get("is_pk", False)
            is_auto = col.get("is_auto", False)

            if is_auto or (is_pk and any(k in col_type for k in ["INT", "SERIAL", "AUTO"])):
                auto_lbl = QLabel("<i>(Auto-Generated Primary Key)</i>")
                auto_lbl.setStyleSheet("color: #64748B; font-size: 9pt;")
                form_layout.addRow(QLabel(f"<b>{col_name}</b> <span style='color:#64748B;'>[{col_type}]</span>:"), auto_lbl)
                continue

            inp = QLineEdit()
            inp.setPlaceholderText(f"Enter {col_name} ({col_type})...")

            # Sensible defaults for realistic data entry
            n_lower = col_name.lower()
            if "first" in n_lower:
                inp.setText("Juan")
            elif "last" in n_lower:
                inp.setText("Dela Cruz")
            elif "age" in n_lower:
                inp.setText("21")
            elif "course" in n_lower or "major" in n_lower:
                inp.setText("Information Technology")
            elif "year" in n_lower:
                inp.setText("2026")
            elif "gpa" in n_lower:
                inp.setText("3.85")
            elif "email" in n_lower:
                inp.setText("juan@example.com")
            elif "status" in n_lower:
                inp.setText("Active")

            form_layout.addRow(QLabel(f"<b>{col_name}</b> <span style='color:#94A3B8;'>[{col_type}]</span>:"), inp)
            self.field_inputs[col_name] = inp

        layout.addLayout(form_layout)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("💾 Save Record")
        self.save_btn.setObjectName("addBtn")
        self.save_btn.clicked.connect(self.accept)
        btn_box.addWidget(self.save_btn)

        layout.addLayout(btn_box)

    def get_record_data(self) -> dict[str, str]:
        """Return non-empty values entered by the user."""
        return {col: inp.text().strip() for col, inp in self.field_inputs.items() if inp.text().strip() != ""}


class CreateTableDialog(QDialog):
    """Visual dialog to create new database tables with starter templates and column builder."""

    TEMPLATES = {
        "Custom Blank Table": [
            ("id", "INT", True, True, True),
            ("name", "VARCHAR(100)", False, False, True),
        ],
        "Students / School": [
            ("student_id", "INT", True, True, True),
            ("first_name", "VARCHAR(100)", False, False, True),
            ("last_name", "VARCHAR(100)", False, False, True),
            ("email", "VARCHAR(120)", False, False, True),
            ("age", "INT", False, False, False),
            ("course", "VARCHAR(100)", False, False, True),
            ("gpa", "DECIMAL(3,2)", False, False, False),
            ("enrollment_date", "DATE", False, False, True),
        ],
        "Courses / University": [
            ("course_id", "INT", True, True, True),
            ("course_code", "VARCHAR(20)", False, False, True),
            ("course_name", "VARCHAR(150)", False, False, True),
            ("credits", "INT", False, False, True),
            ("instructor", "VARCHAR(100)", False, False, True),
            ("department", "VARCHAR(80)", False, False, True),
            ("max_students", "INT", False, False, True),
        ],
        "Products / E-Commerce": [
            ("product_id", "INT", True, True, True),
            ("title", "VARCHAR(150)", False, False, True),
            ("sku", "VARCHAR(50)", False, False, True),
            ("price", "DECIMAL(10,2)", False, False, True),
            ("category", "VARCHAR(50)", False, False, False),
            ("stock_quantity", "INT", False, False, True),
            ("is_active", "BOOLEAN", False, False, True),
        ],
        "Orders / Sales": [
            ("order_id", "INT", True, True, True),
            ("customer_id", "INT", False, False, True),
            ("total_amount", "DECIMAL(10,2)", False, False, True),
            ("status", "VARCHAR(30)", False, False, True),
            ("payment_method", "VARCHAR(50)", False, False, True),
            ("order_date", "TIMESTAMP", False, False, True),
        ],
        "Order Items / Cart": [
            ("item_id", "INT", True, True, True),
            ("order_id", "INT", False, False, True),
            ("product_id", "INT", False, False, True),
            ("quantity", "INT", False, False, True),
            ("unit_price", "DECIMAL(10,2)", False, False, True),
            ("subtotal", "DECIMAL(10,2)", False, False, True),
        ],
        "Customers / CRM": [
            ("customer_id", "INT", True, True, True),
            ("full_name", "VARCHAR(150)", False, False, True),
            ("email", "VARCHAR(120)", False, False, True),
            ("phone", "VARCHAR(30)", False, False, False),
            ("company", "VARCHAR(100)", False, False, False),
            ("city", "VARCHAR(80)", False, False, False),
            ("created_at", "TIMESTAMP", False, False, True),
        ],
        "Users / Accounts": [
            ("user_id", "INT", True, True, True),
            ("username", "VARCHAR(50)", False, False, True),
            ("email", "VARCHAR(120)", False, False, True),
            ("password_hash", "VARCHAR(255)", False, False, True),
            ("role", "VARCHAR(30)", False, False, True),
            ("is_active", "BOOLEAN", False, False, True),
            ("created_at", "TIMESTAMP", False, False, True),
        ],
        "Employees / HR": [
            ("employee_id", "INT", True, True, True),
            ("first_name", "VARCHAR(100)", False, False, True),
            ("last_name", "VARCHAR(100)", False, False, True),
            ("email", "VARCHAR(120)", False, False, True),
            ("department", "VARCHAR(80)", False, False, True),
            ("job_title", "VARCHAR(100)", False, False, True),
            ("salary", "DECIMAL(10,2)", False, False, True),
            ("hire_date", "DATE", False, False, True),
        ],
        "Invoices / Billing": [
            ("invoice_id", "INT", True, True, True),
            ("invoice_number", "VARCHAR(50)", False, False, True),
            ("client_name", "VARCHAR(100)", False, False, True),
            ("amount", "DECIMAL(10,2)", False, False, True),
            ("tax_amount", "DECIMAL(10,2)", False, False, True),
            ("is_paid", "BOOLEAN", False, False, True),
            ("due_date", "DATE", False, False, True),
            ("issued_at", "TIMESTAMP", False, False, True),
        ],
        "Payments / Transactions": [
            ("payment_id", "INT", True, True, True),
            ("order_id", "INT", False, False, True),
            ("amount", "DECIMAL(10,2)", False, False, True),
            ("currency", "VARCHAR(10)", False, False, True),
            ("payment_method", "VARCHAR(40)", False, False, True),
            ("status", "VARCHAR(30)", False, False, True),
            ("transaction_ref", "VARCHAR(100)", False, False, True),
            ("created_at", "TIMESTAMP", False, False, True),
        ],
        "Inventory / Warehouse Stock": [
            ("inventory_id", "INT", True, True, True),
            ("item_name", "VARCHAR(150)", False, False, True),
            ("sku", "VARCHAR(50)", False, False, True),
            ("quantity", "INT", False, False, True),
            ("warehouse_bin", "VARCHAR(50)", False, False, False),
            ("reorder_level", "INT", False, False, True),
            ("last_restocked", "DATE", False, False, False),
        ],
        "Tasks / Project Management": [
            ("task_id", "INT", True, True, True),
            ("title", "VARCHAR(150)", False, False, True),
            ("description", "TEXT", False, False, False),
            ("priority", "VARCHAR(20)", False, False, True),
            ("status", "VARCHAR(30)", False, False, True),
            ("assigned_to", "VARCHAR(100)", False, False, False),
            ("due_date", "DATE", False, False, False),
        ],
        "Support Tickets / Helpdesk": [
            ("ticket_id", "INT", True, True, True),
            ("customer_email", "VARCHAR(120)", False, False, True),
            ("subject", "VARCHAR(150)", False, False, True),
            ("description", "TEXT", False, False, True),
            ("priority", "VARCHAR(20)", False, False, True),
            ("status", "VARCHAR(30)", False, False, True),
            ("created_at", "TIMESTAMP", False, False, True),
        ],
        "Blog Posts / CMS": [
            ("post_id", "INT", True, True, True),
            ("title", "VARCHAR(200)", False, False, True),
            ("slug", "VARCHAR(200)", False, False, True),
            ("content", "TEXT", False, False, True),
            ("author_id", "INT", False, False, True),
            ("status", "VARCHAR(30)", False, False, True),
            ("views_count", "INT", False, False, True),
            ("published_at", "TIMESTAMP", False, False, False),
        ],
        "Comments / Reviews": [
            ("comment_id", "INT", True, True, True),
            ("post_id", "INT", False, False, True),
            ("author_name", "VARCHAR(100)", False, False, True),
            ("author_email", "VARCHAR(120)", False, False, True),
            ("content", "TEXT", False, False, True),
            ("rating", "INT", False, False, False),
            ("created_at", "TIMESTAMP", False, False, True),
        ],
        "Books / Library": [
            ("book_id", "INT", True, True, True),
            ("title", "VARCHAR(200)", False, False, True),
            ("author", "VARCHAR(150)", False, False, True),
            ("isbn", "VARCHAR(25)", False, False, False),
            ("published_year", "INT", False, False, False),
            ("genre", "VARCHAR(50)", False, False, False),
            ("copies_available", "INT", False, False, True),
        ],
        "Events / Bookings": [
            ("event_id", "INT", True, True, True),
            ("event_name", "VARCHAR(150)", False, False, True),
            ("location", "VARCHAR(150)", False, False, True),
            ("start_time", "DATETIME", False, False, True),
            ("end_time", "DATETIME", False, False, True),
            ("capacity", "INT", False, False, True),
            ("ticket_price", "DECIMAL(8,2)", False, False, True),
        ],
        "Hospital / Patients": [
            ("patient_id", "INT", True, True, True),
            ("first_name", "VARCHAR(100)", False, False, True),
            ("last_name", "VARCHAR(100)", False, False, True),
            ("date_of_birth", "DATE", False, False, True),
            ("gender", "VARCHAR(20)", False, False, False),
            ("blood_type", "VARCHAR(10)", False, False, False),
            ("contact_number", "VARCHAR(30)", False, False, False),
            ("emergency_contact", "VARCHAR(100)", False, False, False),
        ],
        "Real Estate / Properties": [
            ("property_id", "INT", True, True, True),
            ("title", "VARCHAR(150)", False, False, True),
            ("property_type", "VARCHAR(50)", False, False, True),
            ("address", "VARCHAR(200)", False, False, True),
            ("price", "DECIMAL(12,2)", False, False, True),
            ("bedrooms", "INT", False, False, False),
            ("bathrooms", "DECIMAL(3,1)", False, False, False),
            ("area_sqft", "INT", False, False, False),
            ("is_available", "BOOLEAN", False, False, True),
        ],
    }

    TEMPLATE_TABLE_NAMES = {
        "Custom Blank Table": "demo_table",
        "Students / School": "students",
        "Courses / University": "courses",
        "Products / E-Commerce": "products",
        "Orders / Sales": "orders",
        "Order Items / Cart": "order_items",
        "Customers / CRM": "customers",
        "Users / Accounts": "users",
        "Employees / HR": "employees",
        "Invoices / Billing": "invoices",
        "Payments / Transactions": "payments",
        "Inventory / Warehouse Stock": "inventory",
        "Tasks / Project Management": "tasks",
        "Support Tickets / Helpdesk": "tickets",
        "Blog Posts / CMS": "posts",
        "Comments / Reviews": "comments",
        "Books / Library": "books",
        "Events / Bookings": "events",
        "Hospital / Patients": "patients",
        "Real Estate / Properties": "properties",
    }

    DATA_TYPES = [
        "INT",
        "VARCHAR(100)",
        "VARCHAR(255)",
        "TEXT",
        "DECIMAL(10,2)",
        "DECIMAL(4,2)",
        "BOOLEAN",
        "DATE",
        "DATETIME",
        "TIMESTAMP",
        "FLOAT",
        "BIGINT",
    ]

    def __init__(self, parent: QWidget, target_db: str = "") -> None:
        super().__init__(parent)
        self.target_db = target_db
        self.setWindowTitle("✨ Create New Table Wizard")
        self.resize(760, 580)
        self.setMinimumSize(680, 500)
        self.setWindowModality(Qt.WindowModality.WindowModal)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Sleek Top Banner
        db_disp = target_db or "Active Database"
        banner = QFrame()
        banner.setStyleSheet("background: #0C101A; border: 1px solid #1A2436; border-radius: 8px; padding: 10px 14px;")
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(0, 0, 0, 0)

        title_lbl = QLabel(
            "<b style='font-size: 11pt; color: #F8FAFC;'>✨ Create New Table Wizard</b><br>"
            "<span style='color: #94A3B8; font-size: 8.5pt;'>Choose an industry starter template or design custom columns visually</span>"
        )
        db_badge = QLabel(f"<b>Database:</b> <span style='color: #38BDF8;'>{db_disp}</span>")
        db_badge.setStyleSheet("background: #141C2B; border: 1px solid #23334D; border-radius: 6px; padding: 4px 10px; font-size: 9pt;")
        banner_layout.addWidget(title_lbl, 1)
        banner_layout.addWidget(db_badge)
        layout.addWidget(banner)

        # Form Controls in a Card
        form_card = QFrame()
        form_card.setStyleSheet("background: #0B0E17; border: 1px solid #1A2436; border-radius: 8px; padding: 8px 12px;")
        form = QFormLayout(form_card)
        form.setSpacing(8)
        form.setContentsMargins(0, 0, 0, 0)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. students, products, orders...")
        self.name_edit.textChanged.connect(self._update_sql_preview)
        form.addRow(QLabel("<b>Table Name:</b>"), self.name_edit)

        self.template_combo = QComboBox()
        self.template_combo.addItems(list(self.TEMPLATES.keys()))
        self.template_combo.currentIndexChanged.connect(self._on_template_changed)
        form.addRow(QLabel("<b>Starter Template:</b>"), self.template_combo)

        layout.addWidget(form_card)

        # Columns Header Row
        col_header_row = QHBoxLayout()
        col_header_row.addWidget(QLabel("<b>Columns & Data Types:</b>"))
        col_header_row.addStretch()

        self.add_col_btn = QPushButton("➕ Add Column")
        self.add_col_btn.setStyleSheet("font-size: 8.5pt; padding: 3px 10px;")
        self.add_col_btn.clicked.connect(self._add_empty_row)
        col_header_row.addWidget(self.add_col_btn)

        self.del_col_btn = QPushButton("➖ Remove Selected")
        self.del_col_btn.setStyleSheet("font-size: 8.5pt; padding: 3px 10px;")
        self.del_col_btn.clicked.connect(self._remove_selected_row)
        col_header_row.addWidget(self.del_col_btn)

        layout.addLayout(col_header_row)

        self.columns_table = QTableWidget(0, 5)
        self.columns_table.setHorizontalHeaderLabels([
            "Column Name", "Type", "Primary Key", "Auto Inc", "Not Null"
        ])
        self.columns_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.columns_table.setColumnWidth(1, 180)
        self.columns_table.setColumnWidth(2, 110)
        self.columns_table.setColumnWidth(3, 95)
        self.columns_table.setColumnWidth(4, 95)
        self.columns_table.setAlternatingRowColors(True)
        self.columns_table.verticalHeader().setDefaultSectionSize(40)
        layout.addWidget(self.columns_table, 1)

        # Live SQL Preview Card
        preview_box = QVBoxLayout()
        preview_box.setSpacing(3)
        preview_lbl = QLabel("<span style='color: #64748B; font-size: 8pt; font-weight: bold;'>LIVE SQL PREVIEW:</span>")
        preview_box.addWidget(preview_lbl)

        self.sql_preview = QPlainTextEdit()
        self.sql_preview.setReadOnly(True)
        self.sql_preview.setMaximumHeight(65)
        self.sql_preview.setStyleSheet(
            "background: #06080F; color: #38BDF8; font-family: 'JetBrains Mono', 'Cascadia Code', monospace; "
            "font-size: 8.5pt; border: 1px solid #1A2538; border-radius: 6px; padding: 6px;"
        )
        preview_box.addWidget(self.sql_preview)
        layout.addLayout(preview_box)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self.cancel_btn)

        self.create_btn = QPushButton("✨ Create Table Now")
        self.create_btn.setObjectName("primaryBtn")
        self.create_btn.setStyleSheet("background: #059669; color: white; font-weight: bold; padding: 7px 18px; border-radius: 6px;")
        self.create_btn.clicked.connect(self._validate_and_accept)
        btn_box.addWidget(self.create_btn)

        layout.addLayout(btn_box)

        self._on_template_changed(0)

    def _wrap_center(self, widget: QWidget) -> QWidget:
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(widget)
        return container

    def _update_sql_preview(self) -> None:
        """Update live DDL preview pane."""
        if not hasattr(self, "sql_preview"):
            return
        _, sql = self.get_create_table_sql()
        self.sql_preview.setPlainText(sql.strip())

    def _add_column_row(self, name: str, col_type: str, pk: bool, ai: bool, nn: bool) -> None:
        r = self.columns_table.rowCount()
        self.columns_table.insertRow(r)

        name_edit = QLineEdit(name)
        name_edit.textChanged.connect(self._update_sql_preview)
        self.columns_table.setCellWidget(r, 0, name_edit)

        combo = QComboBox()
        combo.addItems(self.DATA_TYPES)
        idx = combo.findText(col_type)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.addItem(col_type)
            combo.setCurrentText(col_type)
        combo.currentIndexChanged.connect(self._update_sql_preview)
        self.columns_table.setCellWidget(r, 1, combo)

        pk_cb = QCheckBox()
        pk_cb.setChecked(pk)
        pk_cb.stateChanged.connect(self._update_sql_preview)
        self.columns_table.setCellWidget(r, 2, self._wrap_center(pk_cb))

        ai_cb = QCheckBox()
        ai_cb.setChecked(ai)
        ai_cb.stateChanged.connect(self._update_sql_preview)
        self.columns_table.setCellWidget(r, 3, self._wrap_center(ai_cb))

        nn_cb = QCheckBox()
        nn_cb.setChecked(nn)
        nn_cb.stateChanged.connect(self._update_sql_preview)
        self.columns_table.setCellWidget(r, 4, self._wrap_center(nn_cb))
        self._update_sql_preview()

    def _get_row_data(self, r: int) -> tuple[str, str, bool, bool, bool]:
        name_widget = self.columns_table.cellWidget(r, 0)
        name = name_widget.text().strip() if isinstance(name_widget, QLineEdit) else ""

        type_widget = self.columns_table.cellWidget(r, 1)
        col_type = type_widget.currentText() if isinstance(type_widget, QComboBox) else "VARCHAR(100)"

        pk_container = self.columns_table.cellWidget(r, 2)
        pk_cb = pk_container.findChild(QCheckBox) if pk_container else None
        pk = pk_cb.isChecked() if pk_cb else False

        ai_container = self.columns_table.cellWidget(r, 3)
        ai_cb = ai_container.findChild(QCheckBox) if ai_container else None
        ai = ai_cb.isChecked() if ai_cb else False

        nn_container = self.columns_table.cellWidget(r, 4)
        nn_cb = nn_container.findChild(QCheckBox) if nn_container else None
        nn = nn_cb.isChecked() if nn_cb else False

        return name, col_type, pk, ai, nn

    def _on_template_changed(self, _: int) -> None:
        tpl_key = self.template_combo.currentText()
        cols = self.TEMPLATES.get(tpl_key, [])
        self.columns_table.setRowCount(0)

        cur_name = self.name_edit.text().strip()
        default_names = set(self.TEMPLATE_TABLE_NAMES.values()) | {"demo_table", "new_table"}
        if not cur_name or cur_name in default_names:
            target_name = self.TEMPLATE_TABLE_NAMES.get(tpl_key, "demo_table")
            self.name_edit.setText(target_name)

        for col_name, col_type, pk, ai, nn in cols:
            self._add_column_row(col_name, col_type, pk, ai, nn)
        self._update_sql_preview()

    def _add_empty_row(self) -> None:
        self._add_column_row("new_column", "VARCHAR(100)", False, False, False)
        self._update_sql_preview()

    def _remove_selected_row(self) -> None:
        r = self.columns_table.currentRow()
        if r >= 0:
            self.columns_table.removeRow(r)
            self._update_sql_preview()

    def _validate_and_accept(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Table Name", "Please enter a name for the new table.")
            self.name_edit.setFocus()
            return

        valid_cols = 0
        for r in range(self.columns_table.rowCount()):
            col_name, _, _, _, _ = self._get_row_data(r)
            if col_name:
                valid_cols += 1

        if valid_cols == 0:
            QMessageBox.warning(self, "No Columns", "Please add at least one column to the table.")
            return

        self.accept()

    def get_create_table_sql(self, engine: str = "mysql") -> tuple[str, str]:
        raw_name = self.name_edit.text().strip()
        table_name = re.sub(r"[^\w$]", "_", raw_name)
        if not table_name:
            return "", ""

        col_defs: list[str] = []
        pk_cols: list[str] = []

        for r in range(self.columns_table.rowCount()):
            name, col_type, pk, ai, nn = self._get_row_data(r)
            if not name:
                continue
            clean_col = re.sub(r"[^\w$]", "_", name)

            parts = [f"`{clean_col}`"]
            if engine == "sqlite":
                if pk and ai:
                    parts.append("INTEGER PRIMARY KEY AUTOINCREMENT")
                else:
                    parts.append(col_type)
                    if pk:
                        pk_cols.append(f"`{clean_col}`")
                    if nn:
                        parts.append("NOT NULL")
            else:
                parts.append(col_type)
                if nn:
                    parts.append("NOT NULL")
                if ai:
                    parts.append("AUTO_INCREMENT")
                if pk:
                    pk_cols.append(f"`{clean_col}`")
            col_defs.append("    " + " ".join(parts))

        if pk_cols and engine != "sqlite":
            col_defs.append(f"    PRIMARY KEY ({', '.join(pk_cols)})")

        cols_body = ",\n".join(col_defs)
        if engine == "sqlite":
            sql = f"CREATE TABLE IF NOT EXISTS `{table_name}` (\n{cols_body}\n);"
        else:
            db_prefix = f"`{self.target_db}`." if self.target_db else ""
            sql = f"CREATE TABLE IF NOT EXISTS {db_prefix}`{table_name}` (\n{cols_body}\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"

        return table_name, sql


class SQLStudioWindow(QMainWindow):
    """Main desktop application window for SQLCLI."""

    def __init__(
        self,
        engine_manager: MultiEngineManager,
        settings: Settings,
        mysql_db: Database,
    ) -> None:
        super().__init__()
        self.engine_manager = engine_manager
        self.settings = settings
        self.mysql = mysql_db

        self.last_diagnostic: SQLDiagnostic | None = None
        self.last_headers: list[str] | None = None
        self.last_rows: list[tuple] | None = None
        self.active_table_name: str | None = None
        self.mastered_topics: set[str] = set()
        self._is_populating_grid: bool = False
        self._cell_pre_edit_value: str = ""

        # Prevent Windows DWM from falsely displaying '(Not Responding)' during modal dialogs
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.DisableProcessWindowsGhosting()
            except Exception:
                pass

        self.setWindowTitle("SQLCLI Desktop Studio - Multi-Engine Database Workbench")
        self.resize(1260, 820)
        self.setMinimumSize(900, 540)
        self.setStyleSheet(OBSIDIAN_STYLESHEET)

        # Auto-detect engine on startup
        detected_engine = self.engine_manager.autodetect_active_engine()
        self.last_mysql_online_state: bool = (detected_engine == "mysql")

        self._build_ui()
        self._build_toolbar()
        self._build_statusbar()

        # Wire SQL Completer
        self.completer_model = QStringListModel()
        self.completer = QCompleter(self.completer_model, self)
        self.editor.set_completer(self.completer)

        # Sync combo with auto-detected engine
        engine_map = {"sqlite": 0, "mysql": 1, "nosql": 2}
        self.engine_combo.setCurrentIndex(engine_map.get(detected_engine, 0))

        # Initial schema, database selection, and history refresh
        self._sync_databases_dropdown()
        self.refresh_schema()
        self.refresh_history()

        # Real-time Engine Health Watcher (polls every 8.0s)
        self.health_timer = QTimer(self)
        self.health_timer.setInterval(8000)
        self.health_timer.timeout.connect(self._check_engine_health_realtime)
        self.health_timer.start()

        # Execute initial table preview
        self._run_initial_preview(detected_engine)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main Controls")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Brand Badge
        brand_lbl = QLabel("⚡ SQLCLI Studio")
        brand_lbl.setStyleSheet("font-size: 11pt; font-weight: 800; color: #38BDF8; padding: 0 10px 0 4px;")
        toolbar.addWidget(brand_lbl)

        toolbar.addSeparator()

        # Engine selector
        toolbar.addWidget(QLabel("<b>Engine:</b> "))
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["SQLite (Local)", "MySQL (XAMPP)", "NoSQL (JSON Store)"])
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        toolbar.addWidget(self.engine_combo)

        toolbar.addSeparator()

        # Mode Switcher: TablePlus Data View vs SQL Query Console
        self.mode_data_btn = QPushButton("📊 Data Browser")
        self.mode_data_btn.setObjectName("modeActiveBtn")
        self.mode_data_btn.setToolTip("View and edit table records directly in the spreadsheet (TablePlus style)")
        self.mode_data_btn.clicked.connect(self.switch_to_data_view)
        toolbar.addWidget(self.mode_data_btn)

        self.mode_sql_btn = QPushButton("💻 SQL Editor")
        self.mode_sql_btn.setObjectName("modeInactiveBtn")
        self.mode_sql_btn.setToolTip("Write and execute custom SQL queries, Autopilot, and scripts")
        self.mode_sql_btn.clicked.connect(self.switch_to_sql_view)
        toolbar.addWidget(self.mode_sql_btn)

        toolbar.addSeparator()

        # Visual Table & DB Creators
        self.top_new_table_btn = QPushButton("✨ New Table")
        self.top_new_table_btn.setToolTip("Create a new table visually with starter templates")
        self.top_new_table_btn.setStyleSheet("color: #10B981; font-weight: bold; background: #072219; border: 1px solid #10B981; border-radius: 6px;")
        self.top_new_table_btn.clicked.connect(lambda: self.prompt_create_table())
        toolbar.addWidget(self.top_new_table_btn)

        self.top_new_db_btn = QPushButton("➕ New DB")
        self.top_new_db_btn.setToolTip("Create a new database schema")
        self.top_new_db_btn.setStyleSheet("color: #38BDF8; font-weight: bold; background: #0A1C2E; border: 1px solid #0284C7; border-radius: 6px;")
        self.top_new_db_btn.clicked.connect(self.prompt_create_database)
        toolbar.addWidget(self.top_new_db_btn)

        toolbar.addSeparator()

        # Run query button (SQL mode)
        self.run_btn = QPushButton("▶ Run (F5)")
        self.run_btn.setObjectName("primaryBtn")
        self.run_btn.setToolTip("Execute SQL in Code Editor (F5 or Ctrl+Enter)")
        self.run_btn.clicked.connect(self.run_query)
        toolbar.addWidget(self.run_btn)

        # Auto-fix button
        self.auto_fix_btn = QPushButton("⚡ Auto-Fix (F6)")
        self.auto_fix_btn.setObjectName("fixBtn")
        self.auto_fix_btn.setEnabled(False)
        self.auto_fix_btn.setToolTip("Automatically apply diagnosed fix and re-run")
        self.auto_fix_btn.clicked.connect(self.apply_auto_fix)
        toolbar.addWidget(self.auto_fix_btn)

        # Format SQL
        self.format_btn = QPushButton("🎨 Format")
        self.format_btn.setToolTip("Format and uppercase SQL keywords (Ctrl+B)")
        self.format_btn.clicked.connect(self.format_sql)
        toolbar.addWidget(self.format_btn)

        # Clear editor
        self.clear_btn = QPushButton("🧹 Clear")
        self.clear_btn.setToolTip("Clear the code editor")
        self.clear_btn.clicked.connect(lambda: self.editor.setPlainText(""))
        toolbar.addWidget(self.clear_btn)

        toolbar.addSeparator()

        # Unified Export dropdown button
        self.export_menu_btn = QPushButton("📤 Export ▼")
        self.export_menu = QMenu(self)
        act_csv = self.export_menu.addAction("Export to CSV")
        act_csv.triggered.connect(self.export_csv)
        act_json = self.export_menu.addAction("Export to JSON")
        act_json.triggered.connect(self.export_json)
        act_tsv = self.export_menu.addAction("Copy Table as TSV")
        act_tsv.triggered.connect(self._copy_entire_table_tsv)
        self.export_menu_btn.setMenu(self.export_menu)
        toolbar.addWidget(self.export_menu_btn)

        # Expanding spacer to right-align the live status badge
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        self.engine_badge = QLabel("🟢 MySQL Online (127.0.0.1:3306)")
        self.engine_badge.setStyleSheet("color: #10B981; font-weight: 600; font-size: 8.5pt; background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; padding: 4px 10px;")
        toolbar.addWidget(self.engine_badge)

    def _build_statusbar(self) -> None:
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Auto-detected live database. Ready.")
        self.status_bar.addWidget(self.status_label, 1)

        self.engine_indicator = QLabel("Engine: Auto-Detecting...")
        self.engine_indicator.setStyleSheet("color: #38BDF8; font-weight: bold; padding-right: 12px;")
        self.status_bar.addPermanentWidget(self.engine_indicator)

    def _build_ui(self) -> None:
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(main_splitter)

        # ----------------- LEFT SIDEBAR (Tabs) -----------------
        self.sidebar_tabs = QTabWidget()
        self.sidebar_tabs.setMaximumWidth(460)
        self.sidebar_tabs.setMinimumWidth(280)

        # Tab 1: Database Schema Tree (Single Column: Zero Truncation!)
        schema_widget = QWidget()
        schema_box = QVBoxLayout(schema_widget)
        schema_box.setContentsMargins(6, 6, 6, 6)
        schema_box.setSpacing(6)

        # Database Control Card
        db_card = QFrame()
        db_card.setStyleSheet("background: #0B0E17; border: 1px solid #1E283D; border-radius: 8px; padding: 6px 8px;")
        db_card_box = QVBoxLayout(db_card)
        db_card_box.setContentsMargins(0, 0, 0, 0)
        db_card_box.setSpacing(6)

        schema_db_row = QHBoxLayout()
        schema_db_row.setSpacing(6)
        schema_db_row.addWidget(QLabel("<b>Database:</b>"))

        self.database_combo = QComboBox()
        self.database_combo.setToolTip("Select active database in MySQL")
        self.database_combo.currentIndexChanged.connect(self._on_database_combo_changed)
        schema_db_row.addWidget(self.database_combo, 1)
        db_card_box.addLayout(schema_db_row)

        schema_btn_row = QHBoxLayout()
        schema_btn_row.setSpacing(4)

        self.new_db_btn = QPushButton("➕ New DB")
        self.new_db_btn.setToolTip("Create a new database schema in MySQL")
        self.new_db_btn.setStyleSheet("font-size: 8.5pt; font-weight: bold; color: #38BDF8; background: #0E131F; border: 1px solid #20314D; border-radius: 5px; padding: 4px 6px;")
        self.new_db_btn.clicked.connect(self.prompt_create_database)
        schema_btn_row.addWidget(self.new_db_btn)

        self.drop_db_btn = QPushButton("🗑️ Drop DB")
        self.drop_db_btn.setToolTip("Drop (delete) the selected database permanently")
        self.drop_db_btn.setStyleSheet("font-size: 8.5pt; font-weight: bold; color: #F43F5E; background: #1B0E14; border: 1px solid #4D1A25; border-radius: 5px; padding: 4px 6px;")
        self.drop_db_btn.clicked.connect(lambda: self.prompt_drop_database())
        schema_btn_row.addWidget(self.drop_db_btn)

        self.new_table_btn = QPushButton("✨ New Table")
        self.new_table_btn.setToolTip("Create a new table in the active database")
        self.new_table_btn.setStyleSheet("font-size: 8.5pt; font-weight: bold; color: #10B981; background: #0A1C16; border: 1px solid #144434; border-radius: 5px; padding: 4px 6px;")
        self.new_table_btn.clicked.connect(lambda: self.prompt_create_table())
        schema_btn_row.addWidget(self.new_table_btn)

        self.refresh_schema_btn = QPushButton("🔄")
        self.refresh_schema_btn.setToolTip("Refresh database schema and tables in real-time")
        self.refresh_schema_btn.setFixedWidth(28)
        self.refresh_schema_btn.setStyleSheet("font-size: 9pt; background: #0E131F; border: 1px solid #20314D; border-radius: 5px; padding: 4px;")
        self.refresh_schema_btn.clicked.connect(self.refresh_schema)
        schema_btn_row.addWidget(self.refresh_schema_btn)

        db_card_box.addLayout(schema_btn_row)
        schema_box.addWidget(db_card)

        # Real-time Schema Filter Bar
        self.schema_search = QLineEdit()
        self.schema_search.setPlaceholderText("🔍 Filter tables & columns...")
        self.schema_search.setStyleSheet("font-size: 8.5pt; padding: 4px 8px; border-radius: 5px;")
        self.schema_search.textChanged.connect(self._filter_schema_tree)
        schema_box.addWidget(self.schema_search)

        self.schema_tree = QTreeWidget()
        self.schema_tree.setColumnCount(1)
        self.schema_tree.setHeaderHidden(True)
        self.schema_tree.setIndentation(16)
        self.schema_tree.setAnimated(True)
        self.schema_tree.itemClicked.connect(self._on_schema_item_clicked)
        self.schema_tree.itemDoubleClicked.connect(self._on_schema_item_double_clicked)
        self.schema_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.schema_tree.customContextMenuRequested.connect(self._show_schema_context_menu)
        schema_box.addWidget(self.schema_tree)

        self.sidebar_tabs.addTab(schema_widget, "📁 Tables")

        # Tab 2: Query History
        history_widget = QWidget()
        history_box = QVBoxLayout(history_widget)
        history_box.setContentsMargins(6, 6, 6, 6)
        history_box.setSpacing(6)

        history_top_bar = QHBoxLayout()
        history_top_bar.addWidget(QLabel("<b>Past Queries</b>"))
        history_top_bar.addStretch()
        self.clear_history_btn = QPushButton("🧹 Clear")
        self.clear_history_btn.setToolTip("Clear history records")
        self.clear_history_btn.clicked.connect(self._clear_history)
        history_top_bar.addWidget(self.clear_history_btn)
        history_box.addLayout(history_top_bar)

        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText("🔍 Filter past queries...")
        self.history_search.textChanged.connect(self._filter_history)
        history_box.addWidget(self.history_search)

        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self._on_history_item_double_clicked)
        history_box.addWidget(self.history_list)

        self.sidebar_tabs.addTab(history_widget, "🕒 History")

        # Tab 3: Advanced SQL Academy & Tutor
        self.tutor_widget = QWidget()
        tutor_layout = QVBoxLayout(self.tutor_widget)
        tutor_layout.setContentsMargins(6, 6, 6, 6)
        tutor_layout.setSpacing(6)

        # Search Bar
        self.tutor_search = QLineEdit()
        self.tutor_search.setPlaceholderText("🔍 Search 60+ topics, syntax, or concepts...")
        self.tutor_search.textChanged.connect(self._on_tutor_filter_changed)
        tutor_layout.addWidget(self.tutor_search)

        # Filters Row (Category & Difficulty)
        filters_row = QHBoxLayout()
        filters_row.setSpacing(4)

        self.tutor_cat_combo = QComboBox()
        self.tutor_cat_combo.addItem("All Categories")
        self.tutor_cat_combo.addItems(get_categories())
        self.tutor_cat_combo.currentIndexChanged.connect(self._on_tutor_filter_changed)
        filters_row.addWidget(self.tutor_cat_combo, 2)

        self.tutor_diff_combo = QComboBox()
        self.tutor_diff_combo.addItems(["All Levels", "Beginner", "Intermediate", "Advanced"])
        self.tutor_diff_combo.currentIndexChanged.connect(self._on_tutor_filter_changed)
        filters_row.addWidget(self.tutor_diff_combo, 1)

        tutor_layout.addLayout(filters_row)

        # Topic Selector with Navigation
        topic_row = QHBoxLayout()
        topic_row.setSpacing(4)

        self.tutor_prev_btn = QPushButton("◀")
        self.tutor_prev_btn.setFixedWidth(28)
        self.tutor_prev_btn.setToolTip("Previous topic")
        self.tutor_prev_btn.clicked.connect(self._prev_tutor_topic)
        topic_row.addWidget(self.tutor_prev_btn)

        self.topic_combo = QComboBox()
        self.topic_combo.currentIndexChanged.connect(self._on_tutor_topic_changed)
        topic_row.addWidget(self.topic_combo, 1)

        self.tutor_next_btn = QPushButton("▶")
        self.tutor_next_btn.setFixedWidth(28)
        self.tutor_next_btn.setToolTip("Next topic")
        self.tutor_next_btn.clicked.connect(self._next_tutor_topic)
        topic_row.addWidget(self.tutor_next_btn)

        tutor_layout.addLayout(topic_row)

        # Mastery & Topic Count Bar
        status_bar_row = QHBoxLayout()
        status_bar_row.setContentsMargins(2, 0, 2, 0)

        self.tutor_count_label = QLabel("Showing Topics")
        self.tutor_count_label.setStyleSheet("color: #94A3B8; font-size: 8.5pt;")
        status_bar_row.addWidget(self.tutor_count_label)
        status_bar_row.addStretch()

        self.tutor_mark_done_check = QCheckBox("Mastered")
        self.tutor_mark_done_check.setStyleSheet("color: #38BDF8; font-size: 8.5pt; font-weight: 600;")
        self.tutor_mark_done_check.toggled.connect(self._toggle_topic_mastered)
        status_bar_row.addWidget(self.tutor_mark_done_check)

        tutor_layout.addLayout(status_bar_row)

        # Scroll Area for Rich Educational Detail Cards
        tutor_scroll = QScrollArea()
        tutor_scroll.setWidgetResizable(True)
        tutor_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(2, 4, 4, 4)
        scroll_layout.setSpacing(8)

        # 1. Header Card (Title, Badges, Summary)
        header_card = QFrame()
        header_card.setStyleSheet("background: #0E1017; border: 1px solid #1E293B; border-radius: 6px; padding: 6px;")
        header_card_layout = QVBoxLayout(header_card)
        header_card_layout.setContentsMargins(6, 6, 6, 6)
        header_card_layout.setSpacing(4)

        badges_row = QHBoxLayout()
        badges_row.setSpacing(6)
        self.tutor_title = QLabel("SQL Select")
        self.tutor_title.setStyleSheet("font-size: 11pt; font-weight: bold; color: #38BDF8;")
        badges_row.addWidget(self.tutor_title)
        badges_row.addStretch()

        self.tutor_category_chip = QLabel("BASICS")
        self.tutor_category_chip.setStyleSheet("background: rgba(56, 189, 248, 0.15); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 3px; padding: 1px 5px; font-weight: bold; font-size: 7.5pt;")
        badges_row.addWidget(self.tutor_category_chip)

        self.tutor_difficulty_chip = QLabel("🟢 BEGINNER")
        self.tutor_difficulty_chip.setStyleSheet("background: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 3px; padding: 1px 5px; font-weight: bold; font-size: 7.5pt;")
        badges_row.addWidget(self.tutor_difficulty_chip)
        header_card_layout.addLayout(badges_row)

        self.tutor_summary = QLabel()
        self.tutor_summary.setWordWrap(True)
        self.tutor_summary.setStyleSheet("color: #CBD5E1; font-size: 9pt; line-height: 1.3;")
        header_card_layout.addWidget(self.tutor_summary)
        scroll_layout.addWidget(header_card)

        # 2. Syntax Blueprint Card
        syntax_card = QFrame()
        syntax_card.setStyleSheet("background: #0E1017; border: 1px solid #1E293B; border-radius: 6px; padding: 6px;")
        syntax_layout = QVBoxLayout(syntax_card)
        syntax_layout.setContentsMargins(6, 6, 6, 6)
        syntax_layout.setSpacing(4)

        syntax_header = QHBoxLayout()
        syntax_lbl = QLabel("📐 <b>Syntax Blueprint</b>")
        syntax_lbl.setStyleSheet("color: #F8FAFC; font-size: 9pt;")
        syntax_header.addWidget(syntax_lbl)
        syntax_header.addStretch()

        self.copy_syntax_btn = QPushButton("📋 Copy")
        self.copy_syntax_btn.setFixedSize(56, 22)
        self.copy_syntax_btn.setStyleSheet("font-size: 8pt; padding: 1px 4px;")
        self.copy_syntax_btn.clicked.connect(self._copy_tutor_syntax)
        syntax_header.addWidget(self.copy_syntax_btn)
        syntax_layout.addLayout(syntax_header)

        self.tutor_syntax = QPlainTextEdit()
        self.tutor_syntax.setReadOnly(True)
        self.tutor_syntax.setMaximumHeight(70)
        self.tutor_syntax.setStyleSheet("background: #07080C; border: 1px solid #1F2937; color: #38BDF8; font-family: 'JetBrains Mono', Consolas, monospace; font-size: 8.5pt;")
        syntax_layout.addWidget(self.tutor_syntax)
        scroll_layout.addWidget(syntax_card)

        # 3. Interactive Executable Example Card
        example_card = QFrame()
        example_card.setStyleSheet("background: #0E1017; border: 1px solid #1E293B; border-radius: 6px; padding: 6px;")
        example_layout = QVBoxLayout(example_card)
        example_layout.setContentsMargins(6, 6, 6, 6)
        example_layout.setSpacing(4)

        example_header = QHBoxLayout()
        example_lbl = QLabel("💻 <b>Live Example</b>")
        example_lbl.setStyleSheet("color: #F8FAFC; font-size: 9pt;")
        example_header.addWidget(example_lbl)
        example_header.addStretch()

        self.copy_example_btn = QPushButton("📋 Copy")
        self.copy_example_btn.setFixedSize(56, 22)
        self.copy_example_btn.setStyleSheet("font-size: 8pt; padding: 1px 4px;")
        self.copy_example_btn.clicked.connect(self._copy_tutor_example)
        example_header.addWidget(self.copy_example_btn)
        example_layout.addLayout(example_header)

        self.tutor_example = QPlainTextEdit()
        self.tutor_example.setReadOnly(True)
        self.tutor_example.setMaximumHeight(85)
        self.tutor_example.setStyleSheet("background: #07080C; border: 1px solid #1F2937; color: #34D399; font-family: 'JetBrains Mono', Consolas, monospace; font-size: 8.5pt;")
        example_layout.addWidget(self.tutor_example)

        # Action Buttons Row
        actions_row = QHBoxLayout()
        actions_row.setSpacing(4)

        self.run_tutor_live_btn = QPushButton("▶ Run Live (F5)")
        self.run_tutor_live_btn.setStyleSheet("background: #0284C7; color: white; font-weight: bold; font-size: 8.5pt; padding: 4px;")
        self.run_tutor_live_btn.clicked.connect(self._run_tutor_example_live)
        actions_row.addWidget(self.run_tutor_live_btn, 1)

        self.adapt_tutor_btn = QPushButton("⚡ Adapt to Active Table")
        self.adapt_tutor_btn.setStyleSheet("background: #D97706; color: white; font-weight: bold; font-size: 8.5pt; padding: 4px;")
        self.adapt_tutor_btn.clicked.connect(self._adapt_tutor_example_to_active_table)
        actions_row.addWidget(self.adapt_tutor_btn, 1)

        example_layout.addLayout(actions_row)

        self.load_tutor_btn = QPushButton("📥 Load into Editor")
        self.load_tutor_btn.setStyleSheet("font-size: 8.5pt; padding: 3px;")
        self.load_tutor_btn.clicked.connect(self._load_tutor_example_into_editor)
        example_layout.addWidget(self.load_tutor_btn)
        scroll_layout.addWidget(example_card)

        # 4. Best Practices & Gotchas Callout
        notes_card = QFrame()
        notes_card.setStyleSheet("background: rgba(245, 158, 11, 0.08); border-left: 3px solid #F59E0B; border-radius: 4px; padding: 6px;")
        notes_layout = QVBoxLayout(notes_card)
        notes_layout.setContentsMargins(6, 6, 6, 6)
        notes_layout.setSpacing(3)

        notes_lbl = QLabel("⚠️ <b>Best Practices & Pitfalls</b>")
        notes_lbl.setStyleSheet("color: #F59E0B; font-size: 9pt;")
        notes_layout.addWidget(notes_lbl)

        self.tutor_notes = QLabel()
        self.tutor_notes.setWordWrap(True)
        self.tutor_notes.setStyleSheet("color: #FDE68A; font-size: 8.5pt;")
        notes_layout.addWidget(self.tutor_notes)
        scroll_layout.addWidget(notes_card)

        # 5. Practice Mission Card
        mission_card = QFrame()
        mission_card.setStyleSheet("background: rgba(129, 140, 248, 0.08); border-left: 3px solid #818CF8; border-radius: 4px; padding: 6px;")
        mission_layout = QVBoxLayout(mission_card)
        mission_layout.setContentsMargins(6, 6, 6, 6)
        mission_layout.setSpacing(3)

        mission_lbl = QLabel("🎯 <b>Practice Mission</b>")
        mission_lbl.setStyleSheet("color: #818CF8; font-size: 9pt;")
        mission_layout.addWidget(mission_lbl)

        self.tutor_challenge_desc = QLabel()
        self.tutor_challenge_desc.setWordWrap(True)
        self.tutor_challenge_desc.setStyleSheet("color: #C7D2FE; font-size: 8.5pt;")
        mission_layout.addWidget(self.tutor_challenge_desc)

        mission_btns = QHBoxLayout()
        mission_btns.setSpacing(4)

        self.load_challenge_btn = QPushButton("🎯 Load Mission")
        self.load_challenge_btn.setStyleSheet("font-size: 8pt; padding: 2px 4px;")
        self.load_challenge_btn.clicked.connect(self._load_challenge_into_editor)
        mission_btns.addWidget(self.load_challenge_btn)

        self.show_solution_btn = QPushButton("💡 Solution")
        self.show_solution_btn.setStyleSheet("font-size: 8pt; padding: 2px 4px;")
        self.show_solution_btn.clicked.connect(self._show_tutor_solution)
        mission_btns.addWidget(self.show_solution_btn)

        mission_layout.addLayout(mission_btns)
        scroll_layout.addWidget(mission_card)

        scroll_layout.addStretch()
        tutor_scroll.setWidget(scroll_content)
        tutor_layout.addWidget(tutor_scroll, 1)

        self._populate_tutor_topics()

        self.sidebar_tabs.addTab(self.tutor_widget, "📚 SQL Tutor")
        main_splitter.addWidget(self.sidebar_tabs)

        # ----------------- RIGHT WORKSPACE (QStackedWidget: Data View vs SQL Console) -----------------
        self.main_stack = QStackedWidget()
        main_splitter.addWidget(self.main_stack)

        # ----------------- PAGE 0: DATA BROWSER (TABLEPLUS STYLE) -----------------
        data_view_container = QWidget()
        data_view_layout = QVBoxLayout(data_view_container)
        data_view_layout.setContentsMargins(6, 6, 6, 6)
        data_view_layout.setSpacing(6)

        # Clean Table Action Bar
        data_action_bar = QHBoxLayout()
        data_action_bar.setSpacing(8)

        self.data_view_title = QLabel("📄 <b>No Table Selected</b>")
        self.data_view_title.setStyleSheet("font-size: 11pt; color: #F8FAFC; font-weight: bold;")
        data_action_bar.addWidget(self.data_view_title)

        self.data_view_count = QLabel("")
        self.data_view_count.setStyleSheet("color: #94A3B8; font-size: 10pt;")
        data_action_bar.addWidget(self.data_view_count)

        data_action_bar.addSpacing(10)

        # Direct Record Actions (No SQL typing required!)
        self.add_record_btn = QPushButton("➕ Add Record")
        self.add_record_btn.setObjectName("addBtn")
        self.add_record_btn.setToolTip("Add a new record to this table via form dialog")
        self.add_record_btn.clicked.connect(self.add_new_record)
        data_action_bar.addWidget(self.add_record_btn)

        self.new_table_data_btn = QPushButton("✨ New Table")
        self.new_table_data_btn.setToolTip("Create a new table in the active database")
        self.new_table_data_btn.setStyleSheet("color: #10B981; font-weight: bold;")
        self.new_table_data_btn.clicked.connect(lambda: self.prompt_create_table())
        data_action_bar.addWidget(self.new_table_data_btn)

        self.delete_record_btn = QPushButton("🗑️ Delete Selected")
        self.delete_record_btn.setObjectName("deleteBtn")
        self.delete_record_btn.setToolTip("Delete currently selected record(s) from database")
        self.delete_record_btn.clicked.connect(self.delete_selected_records)
        data_action_bar.addWidget(self.delete_record_btn)

        self.refresh_data_btn = QPushButton("🔄 Refresh")
        self.refresh_data_btn.setToolTip("Reload records from database in real time")
        self.refresh_data_btn.clicked.connect(lambda: self.load_table_data(self._get_active_table_name() or ""))
        data_action_bar.addWidget(self.refresh_data_btn)

        data_action_bar.addStretch()

        # Real-time search filter for spreadsheet
        self.table_filter_input = QLineEdit()
        self.table_filter_input.setPlaceholderText("🔍 Filter displayed rows in real-time...")
        self.table_filter_input.setFixedWidth(280)
        self.table_filter_input.textChanged.connect(self._filter_results_table)
        data_action_bar.addWidget(self.table_filter_input)

        self.copy_table_btn = QPushButton("📋 Copy TSV")
        self.copy_table_btn.setToolTip("Copy entire table to clipboard as TSV")
        self.copy_table_btn.clicked.connect(self._copy_entire_table_tsv)
        data_action_bar.addWidget(self.copy_table_btn)

        data_view_layout.addLayout(data_action_bar)

        # Full-height Spreadsheet Grid with inline editing & smooth scrollbars
        self.table_widget = QTableWidget()
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.horizontalHeader().setStretchLastSection(True)
        self.table_widget.horizontalHeader().setSectionsClickable(True)
        self.table_widget.horizontalHeader().setSortIndicatorShown(True)
        self.table_widget.verticalHeader().setVisible(True)
        self.table_widget.verticalHeader().setDefaultSectionSize(32)
        self.table_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_widget.customContextMenuRequested.connect(self._show_table_context_menu)
        self.table_widget.cellEntered.connect(self._on_table_cell_entered)
        self.table_widget.itemChanged.connect(self._on_table_item_changed)
        data_view_layout.addWidget(self.table_widget, 1)

        self.main_stack.addWidget(data_view_container)

        # ----------------- PAGE 1: SQL QUERY CONSOLE -----------------
        sql_view_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top area: Autopilot Bar + Dynamic Quick Actions + Code Editor + Error HUD
        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(6, 6, 6, 6)
        top_layout.setSpacing(6)

        # Autopilot Bar
        autopilot_box = QHBoxLayout()
        autopilot_box.setSpacing(6)
        autopilot_label = QLabel("✈ <b>Autopilot:</b>")
        autopilot_label.setStyleSheet("color: #38BDF8; font-size: 10pt;")
        autopilot_box.addWidget(autopilot_label)

        self.autopilot_input = QLineEdit()
        self.autopilot_input.setPlaceholderText("Ask in plain English (e.g. 'show all students' or 'count records') and press Enter...")
        self.autopilot_input.returnPressed.connect(self.run_autopilot)
        self.autopilot_model = QStringListModel()
        self.autopilot_completer = QCompleter(self.autopilot_model, self)
        self.autopilot_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.autopilot_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        auto_popup = self.autopilot_completer.popup()
        if auto_popup:
            auto_popup.setObjectName("completerPopup")
        self.autopilot_input.setCompleter(self.autopilot_completer)
        autopilot_box.addWidget(self.autopilot_input)

        self.autopilot_btn = QPushButton("Generate & Run")
        self.autopilot_btn.setToolTip("Convert English request to SQL and run")
        self.autopilot_btn.clicked.connect(self.run_autopilot)
        autopilot_box.addWidget(self.autopilot_btn)
        top_layout.addLayout(autopilot_box)

        # Dynamic Quick Action Chips
        chips_box = QHBoxLayout()
        chips_box.setSpacing(6)
        self.chips_label = QLabel("💡 <b>Quick Actions:</b>")
        self.chips_label.setStyleSheet("color: #94A3B8; font-size: 9pt;")
        chips_box.addWidget(self.chips_label)

        self.chip_view_btn = QPushButton("🔍 View Data (Top 50)")
        self.chip_view_btn.setProperty("class", "chipBtn")
        self.chip_view_btn.clicked.connect(self._action_view_top_data)
        chips_box.addWidget(self.chip_view_btn)

        self.chip_count_btn = QPushButton("🔢 Count Rows")
        self.chip_count_btn.setProperty("class", "chipBtn")
        self.chip_count_btn.clicked.connect(self._action_count_rows)
        chips_box.addWidget(self.chip_count_btn)

        self.chip_desc_btn = QPushButton("📋 Describe Structure")
        self.chip_desc_btn.setProperty("class", "chipBtn")
        self.chip_desc_btn.clicked.connect(self._action_describe_table)
        chips_box.addWidget(self.chip_desc_btn)

        self.chip_insert_btn = QPushButton("➕ Insert Template")
        self.chip_insert_btn.setProperty("class", "chipBtn")
        self.chip_insert_btn.clicked.connect(self._action_insert_template)
        chips_box.addWidget(self.chip_insert_btn)

        self.chip_create_btn = QPushButton("✨ Create Table Wizard")
        self.chip_create_btn.setProperty("class", "chipBtn")
        self.chip_create_btn.setToolTip("Open visual table creation wizard with 20 starter templates")
        self.chip_create_btn.clicked.connect(lambda: self.prompt_create_table())
        chips_box.addWidget(self.chip_create_btn)

        chips_box.addStretch()
        top_layout.addLayout(chips_box)

        # Code Editor
        self.editor = CodeEditor()
        self.editor.on_run_requested = self.run_query
        top_layout.addWidget(self.editor, 1)

        # Error Diagnostics HUD
        self.error_frame = QFrame()
        self.error_frame.setObjectName("errorFrame")
        self.error_frame.setStyleSheet("""
            QFrame#errorFrame {
                background-color: #1A0D11;
                border: 1px solid #E11D48;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        error_layout = QVBoxLayout(self.error_frame)
        error_layout.setContentsMargins(12, 10, 12, 10)
        error_layout.setSpacing(4)

        self.error_title = QLabel("✖ <b>EXECUTION ERROR</b>")
        self.error_title.setStyleSheet("color: #F43F5E; font-size: 11pt; font-weight: bold;")
        error_layout.addWidget(self.error_title)

        self.error_problem = QLabel()
        self.error_problem.setWordWrap(True)
        self.error_problem.setStyleSheet("color: #F8FAFC; font-weight: 600; font-size: 10pt;")
        error_layout.addWidget(self.error_problem)

        self.error_why = QLabel()
        self.error_why.setWordWrap(True)
        self.error_why.setStyleSheet("color: #94A3B8;")
        error_layout.addWidget(self.error_why)

        self.error_rule = QLabel()
        self.error_rule.setWordWrap(True)
        self.error_rule.setStyleSheet("color: #38BDF8; font-weight: 500;")
        error_layout.addWidget(self.error_rule)

        hud_action_box = QHBoxLayout()
        hud_action_box.setSpacing(8)
        self.hud_fix_btn = QPushButton("⚡ Apply Auto-Fix & Rerun (F6)")
        self.hud_fix_btn.setObjectName("fixBtn")
        self.hud_fix_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hud_fix_btn.clicked.connect(self.apply_auto_fix)
        hud_action_box.addWidget(self.hud_fix_btn)

        self.hud_tutorial_btn = QPushButton("📖 Learn on W3Schools")
        self.hud_tutorial_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hud_tutorial_btn.clicked.connect(self._open_tutorial_for_error)
        hud_action_box.addWidget(self.hud_tutorial_btn)

        self.hud_dismiss_btn = QPushButton("Dismiss")
        self.hud_dismiss_btn.clicked.connect(lambda: self.error_frame.setVisible(False))
        hud_action_box.addWidget(self.hud_dismiss_btn)
        hud_action_box.addStretch()

        error_layout.addLayout(hud_action_box)
        self.error_frame.setVisible(False)
        top_layout.addWidget(self.error_frame)

        sql_view_splitter.addWidget(top_container)

        # Bottom area: Query Results Table
        query_bottom_container = QWidget()
        query_bottom_layout = QVBoxLayout(query_bottom_container)
        query_bottom_layout.setContentsMargins(6, 6, 6, 6)
        query_bottom_layout.setSpacing(6)

        results_header = QHBoxLayout()
        results_header.setSpacing(8)
        self.results_title = QLabel("📊 <b>Query Results Grid</b>")
        results_header.addWidget(self.results_title)

        self.results_count_label = QLabel("(No query executed yet)")
        self.results_count_label.setStyleSheet("color: #94A3B8;")
        results_header.addWidget(self.results_count_label)
        results_header.addStretch()

        query_bottom_layout.addLayout(results_header)

        self.query_table_widget = QTableWidget()
        self.query_table_widget.setAlternatingRowColors(True)
        self.query_table_widget.horizontalHeader().setStretchLastSection(True)
        self.query_table_widget.horizontalHeader().setSectionsClickable(True)
        self.query_table_widget.verticalHeader().setVisible(True)
        self.query_table_widget.verticalHeader().setDefaultSectionSize(32)
        query_bottom_layout.addWidget(self.query_table_widget, 1)

        sql_view_splitter.addWidget(query_bottom_container)
        sql_view_splitter.setSizes([380, 440])

        self.main_stack.addWidget(sql_view_splitter)

        # Set default sizes and view
        main_splitter.setSizes([300, 960])
        self.main_stack.setCurrentIndex(0)
        self._on_tutor_topic_changed(0)

    def switch_to_data_view(self) -> None:
        """Switch to full-height TablePlus Data Browser."""
        self.main_stack.setCurrentIndex(0)
        self.mode_data_btn.setObjectName("modeActiveBtn")
        self.mode_sql_btn.setObjectName("modeInactiveBtn")
        self.mode_data_btn.style().unpolish(self.mode_data_btn)
        self.mode_data_btn.style().polish(self.mode_data_btn)
        self.mode_sql_btn.style().unpolish(self.mode_sql_btn)
        self.mode_sql_btn.style().polish(self.mode_sql_btn)

    def switch_to_sql_view(self) -> None:
        """Switch to SQL Query Editor and Scratchpad."""
        self.main_stack.setCurrentIndex(1)
        self.mode_sql_btn.setObjectName("modeActiveBtn")
        self.mode_data_btn.setObjectName("modeInactiveBtn")
        self.mode_sql_btn.style().unpolish(self.mode_sql_btn)
        self.mode_sql_btn.style().polish(self.mode_sql_btn)
        self.mode_data_btn.style().unpolish(self.mode_data_btn)
        self.mode_data_btn.style().polish(self.mode_data_btn)

    def _run_initial_preview(self, engine: str) -> None:
        """Load real table data immediately into Data Browser on start."""
        if engine == "mysql" and self.settings.database:
            schema = self.engine_manager.mysql.tables
            first_tbl = next(iter(schema.keys()), None) if schema else None
            if first_tbl:
                self.load_table_data(first_tbl)
                self.editor.setPlainText(f"SELECT * FROM `{first_tbl}` LIMIT 50;\n")
                return

        # SQLite fallback or demo
        schema = self.engine_manager.get_schema(engine)
        first_tbl = next(iter(schema.keys()), None) if schema else None
        if first_tbl:
            self.load_table_data(first_tbl)
            self.editor.setPlainText(f"SELECT * FROM `{first_tbl}` LIMIT 50;\n")
        else:
            self.editor.setPlainText(
                "-- Welcome to SQLCLI Desktop Studio!\n"
                "-- Autodetected active engine. Click any table or run queries below.\n"
                "SELECT 1 AS status, 'Studio Ready' AS message;\n"
            )
            self.run_query()

    def closeEvent(self, event: Any) -> None:
        if hasattr(self, "health_timer"):
            self.health_timer.stop()
        super().closeEvent(event)

    def _check_engine_health_realtime(self) -> None:
        """Periodically probe MySQL server health and update status badge in real time."""
        if QApplication.activeModalWidget() is not None:
            return
        is_mysql_online = self.engine_manager.check_mysql_status()
        if is_mysql_online != self.last_mysql_online_state:
            self.last_mysql_online_state = is_mysql_online
            if is_mysql_online:
                self.engine_badge.setText("🟢 MySQL Online (127.0.0.1:3306)")
                self.engine_badge.setStyleSheet("color: #10B981; font-weight: 600; font-size: 8.5pt; background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; padding: 4px 10px;")
                if self.engine_manager.active_engine == "mysql":
                    self._sync_databases_dropdown()
                    self.refresh_schema()
            else:
                self.engine_badge.setText("🔴 MySQL Offline (XAMPP)")
                self.engine_badge.setStyleSheet("color: #F43F5E; font-weight: 600; font-size: 8.5pt; background: rgba(244, 63, 94, 0.12); border: 1px solid rgba(244, 63, 94, 0.3); border-radius: 12px; padding: 4px 10px;")

    def _sync_databases_dropdown(self) -> None:
        """Populate database selector combo box with available databases."""
        self.database_combo.blockSignals(True)
        self.database_combo.clear()
        eng = self.engine_manager.active_engine

        if eng == "mysql":
            dbs = self.engine_manager.get_mysql_databases()
            if not dbs and self.engine_manager.check_mysql_status():
                dbs = ["(no databases)"]
            for db in dbs:
                self.database_combo.addItem(db)

            current_db = self.settings.database
            if current_db and current_db in dbs:
                self.database_combo.setCurrentText(current_db)
            elif dbs and dbs[0] != "(no databases)":
                self.database_combo.setCurrentIndex(0)
                self.settings.database = dbs[0]
                try:
                    self.mysql.connect(dbs[0])
                except Exception:
                    pass
        elif eng == "sqlite":
            self.database_combo.addItem(self.engine_manager.sqlite.db_path.name)
        else:
            self.database_combo.addItem(self.engine_manager.nosql.db_path.name)

        self.database_combo.blockSignals(False)

    def _on_database_combo_changed(self, index: int) -> None:
        eng = self.engine_manager.active_engine
        if eng != "mysql":
            return
        selected_db = self.database_combo.currentText().strip()
        if not selected_db or selected_db.startswith("("):
            return
        try:
            self.mysql.connect(selected_db)
            self.settings.database = selected_db
            self.refresh_schema()
            self.status_label.setText(f"✓ Switched to database '{selected_db}'.")
            self.engine_indicator.setText(f"Engine: MYSQL ({selected_db})")

            # Load first table in the selected database into Data View
            schema = self.engine_manager.mysql.tables
            first_tbl = next(iter(schema.keys()), None) if schema else None
            if first_tbl:
                self.load_table_data(first_tbl)
        except Exception as exc:
            self.status_label.setText(f"Failed to switch database: {exc}")

    def _on_engine_changed(self, index: int) -> None:
        engines = ["sqlite", "mysql", "nosql"]
        target = engines[index]
        self.engine_manager.active_engine = target

        if target == "mysql":
            if not self.engine_manager.check_mysql_status():
                self.status_label.setText("⚠ MySQL is offline. Start MySQL in XAMPP.")
                self.engine_indicator.setText("Engine: MYSQL (Offline)")
            else:
                self.engine_manager.autodetect_active_engine()
                db_name = self.settings.database or "mysql"
                self.engine_indicator.setText(f"Engine: MYSQL ({db_name})")
                self.status_label.setText(f"Connected to MySQL on {self.settings.host}:{self.settings.port}.")
        elif target == "sqlite":
            self.engine_indicator.setText(f"Engine: SQLITE ({self.engine_manager.sqlite.db_path.name})")
            self.status_label.setText(f"Switched engine to SQLITE ({self.engine_manager.sqlite.db_path.name}).")
        else:
            self.engine_indicator.setText(f"Engine: NOSQL ({self.engine_manager.nosql.db_path.name})")
            self.status_label.setText(f"Switched engine to NOSQL ({self.engine_manager.nosql.db_path.name}).")

        self._sync_databases_dropdown()
        self.refresh_schema()

    def refresh_schema(self) -> None:
        """Populate database tree explorer without truncation and with full types."""
        self.schema_tree.clear()
        eng = self.engine_manager.active_engine
        words = [
            # Queries & Clauses
            "SELECT", "SELECT DISTINCT", "FROM", "WHERE", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "OFFSET",
            "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN", "CROSS JOIN", "ON", "AS",
            "AND", "OR", "NOT", "IN", "BETWEEN", "LIKE", "IS NULL", "IS NOT NULL",
            "ASC", "DESC", "UNION", "UNION ALL", "CASE", "WHEN", "THEN", "ELSE", "END", "EXISTS",
            # DML Mutations
            "INSERT INTO", "VALUES", "UPDATE", "SET", "DELETE FROM", "REPLACE INTO",
            # DDL Schema
            "CREATE TABLE IF NOT EXISTS", "CREATE TABLE", "DROP TABLE IF EXISTS", "DROP TABLE",
            "ALTER TABLE", "ADD COLUMN", "DROP COLUMN", "MODIFY COLUMN", "RENAME TO", "TRUNCATE",
            "CREATE DATABASE IF NOT EXISTS", "CREATE DATABASE", "DROP DATABASE IF EXISTS", "DROP DATABASE",
            "USE", "DESCRIBE", "SHOW DATABASES", "SHOW TABLES", "SHOW COLUMNS FROM",
            "PRIMARY KEY", "FOREIGN KEY", "REFERENCES", "AUTO_INCREMENT", "AUTOINCREMENT",
            "UNIQUE", "NOT NULL", "DEFAULT", "CHECK", "CONSTRAINT", "CASCADE",
            # Built-in Aggregate & Scalar Functions
            "COUNT(*)", "COUNT()", "SUM()", "AVG()", "MIN()", "MAX()", "ROUND()", "FLOOR()", "CEIL()", "ABS()",
            "CONCAT()", "CONCAT_WS()", "SUBSTRING()", "REPLACE()", "TRIM()", "LOWER()", "UPPER()", "LENGTH()",
            "NOW()", "CURDATE()", "CURTIME()", "DATEDIFF()", "DATE_ADD()", "DATE_SUB()", "DATE_FORMAT()",
            "COALESCE()", "IFNULL()", "NULLIF()", "IF()", "GROUP_CONCAT()", "JSON_EXTRACT()",
            # Data Types
            "INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "VARCHAR(255)", "VARCHAR(100)", "VARCHAR(50)",
            "TEXT", "DECIMAL(10, 2)", "FLOAT", "DOUBLE", "BOOLEAN", "DATE", "DATETIME", "TIMESTAMP", "JSON",
            # NoSQL Commands
            "show collections", "db.find()", "db.insert()", "db.delete()",
        ]

        schema_cols_map: dict[str, list[str]] = {}

        if eng == "mysql":
            multi_details = self.engine_manager.get_mysql_multi_schema_details()
            current_db = self.settings.database or ""

            for db_name, tables in multi_details.items():
                words.append(db_name)
                is_active = db_name.lower() == current_db.lower()
                badge = " (active)" if is_active else ""
                root_item = QTreeWidgetItem([f"📁 {db_name}{badge} ({len(tables)} tables)"])
                root_item.setData(0, Qt.ItemDataRole.UserRole, f"db:{db_name}")
                root_item.setExpanded(is_active)
                if is_active:
                    root_item.setForeground(0, QColor("#38BDF8"))
                self.schema_tree.addTopLevelItem(root_item)

                for tbl, cols_info in tables.items():
                    words.append(tbl)
                    col_names = [c["name"] for c in cols_info]
                    schema_cols_map[tbl] = col_names
                    tbl_item = QTreeWidgetItem([f"  📄 {tbl} ({len(cols_info)} cols)"])
                    tbl_item.setData(0, Qt.ItemDataRole.UserRole, f"table:{db_name}:{tbl}")
                    tbl_item.setExpanded(is_active)
                    for c_dict in cols_info:
                        col_name = c_dict["name"]
                        col_type = c_dict["type"]
                        pk_tag = " [PK]" if c_dict.get("is_pk") else ""
                        words.append(col_name)
                        words.append(f"{tbl}.{col_name}")
                        col_item = QTreeWidgetItem([f"      • {col_name}  ·  {col_type}{pk_tag}"])
                        col_item.setData(0, Qt.ItemDataRole.UserRole, f"col:{col_name}:{col_type}")
                        tbl_item.addChild(col_item)
                    root_item.addChild(tbl_item)
        elif eng == "sqlite":
            details = self.engine_manager.sqlite.get_schema_details()
            root_item = QTreeWidgetItem([f"📁 Database [SQLITE] ({len(details)} tables)"])
            root_item.setExpanded(True)
            self.schema_tree.addTopLevelItem(root_item)

            for tbl, cols_info in details.items():
                words.append(tbl)
                col_names = [c["name"] for c in cols_info]
                schema_cols_map[tbl] = col_names
                tbl_item = QTreeWidgetItem([f"  📄 {tbl} ({len(cols_info)} cols)"])
                tbl_item.setData(0, Qt.ItemDataRole.UserRole, f"table::{tbl}")
                tbl_item.setExpanded(True)
                for c_dict in cols_info:
                    col_name = c_dict["name"]
                    col_type = c_dict["type"]
                    pk_tag = " [PK]" if c_dict.get("is_pk") else ""
                    words.append(col_name)
                    words.append(f"{tbl}.{col_name}")
                    col_item = QTreeWidgetItem([f"      • {col_name}  ·  {col_type}{pk_tag}"])
                    col_item.setData(0, Qt.ItemDataRole.UserRole, f"col:{col_name}:{col_type}")
                    tbl_item.addChild(col_item)
                root_item.addChild(tbl_item)
        else:
            schema = self.engine_manager.nosql.get_schema()
            root_item = QTreeWidgetItem([f"📁 Database [NOSQL] ({len(schema)} collections)"])
            root_item.setExpanded(True)
            self.schema_tree.addTopLevelItem(root_item)

            for tbl, cols in schema.items():
                words.append(tbl)
                words.append(f"db.{tbl}.find()")
                words.append(f"db.{tbl}.insert()")
                words.append(f"db.{tbl}.delete()")
                schema_cols_map[tbl] = cols
                tbl_item = QTreeWidgetItem([f"  📄 {tbl} ({len(cols)} fields)"])
                tbl_item.setData(0, Qt.ItemDataRole.UserRole, f"table::{tbl}")
                tbl_item.setExpanded(True)
                for col in cols:
                    words.append(col)
                    words.append(f"{tbl}.{col}")
                    col_item = QTreeWidgetItem([f"      • {col}"])
                    col_item.setData(0, Qt.ItemDataRole.UserRole, f"col:{col}:ANY")
                    tbl_item.addChild(col_item)
                root_item.addChild(tbl_item)

        self.editor.schema_columns = schema_cols_map
        self.editor.all_words = sorted(list(set(words)))
        if hasattr(self, "completer_model"):
            self.completer_model.setStringList(self.editor.all_words)

        # Dynamic live Autopilot prompt suggestions
        auto_prompts = [
            "create database my_workspace",
            "create table users with first name, last name, email, password, and age",
            "create table products with title, price, category, stock",
            "top 10 highest paid employees",
        ]
        for tbl, cols in schema_cols_map.items():
            auto_prompts.append(f"show all {tbl}")
            auto_prompts.append(f"count records in {tbl}")
            auto_prompts.append(f"top 10 {tbl} ordered by id")
            auto_prompts.append(f"find duplicates in {tbl}")
            auto_prompts.append(f"{tbl} created today")
            auto_prompts.append(f"{tbl} in the past week")
            if len(cols) >= 2:
                auto_prompts.append(f"create table {tbl}_backup with {', '.join(cols[:4])}")
        if len(schema_cols_map) >= 2:
            tbl_names = list(schema_cols_map.keys())
            auto_prompts.append(f"join {tbl_names[0]} and {tbl_names[1]}")

        if hasattr(self, "autopilot_model"):
            self.autopilot_model.setStringList(sorted(list(set(auto_prompts))))

        if hasattr(self, "schema_search") and self.schema_search.text().strip():
            self._filter_schema_tree(self.schema_search.text())

    def _get_active_table_name(self) -> str | None:
        """Find the active or selected table name."""
        if self.active_table_name:
            return self.active_table_name

        eng = self.engine_manager.active_engine
        if eng == "mysql":
            schema = self.engine_manager.mysql.tables
            if schema:
                return next(iter(schema.keys()))
        else:
            schema = self.engine_manager.get_schema(eng)
            if schema:
                return next(iter(schema.keys()))
        return None

    def _get_table_columns_info(self, table_name: str) -> list[dict[str, Any]]:
        """Retrieve column names, types, and primary key status for the active table."""
        eng = self.engine_manager.active_engine
        if eng == "mysql":
            multi = self.engine_manager.get_mysql_multi_schema_details()
            curr_db = self.settings.database or ""
            if curr_db in multi and table_name in multi[curr_db]:
                return multi[curr_db][table_name]
            for db, tables in multi.items():
                if table_name in tables:
                    return tables[table_name]
        elif eng == "sqlite":
            details = self.engine_manager.sqlite.get_schema_details()
            if table_name in details:
                return details[table_name]

        # Fallback from current table headers
        headers = [
            self.table_widget.horizontalHeaderItem(c).text()
            for c in range(self.table_widget.columnCount())
            if self.table_widget.horizontalHeaderItem(c)
        ]
        return [{"name": h, "type": "TEXT", "is_pk": False, "is_auto": False} for h in headers]

    def _escape_sql(self, val: str) -> str:
        """Escape single quotes and backslashes safely for SQL strings."""
        escaped = val.replace("'", "''")
        if self.engine_manager.active_engine == "mysql":
            escaped = escaped.replace("\\", "\\\\")
        return escaped

    def load_table_data(self, table_name: str) -> None:
        """TablePlus core: Load live table records into the spreadsheet grid."""
        if not table_name:
            return
        self.active_table_name = table_name
        eng = self.engine_manager.active_engine

        if eng == "nosql":
            query = f"db.{table_name}.find();"
        else:
            query = f"SELECT * FROM `{table_name}` LIMIT 250;"

        headers, rows, count, elapsed_ms, err = self.engine_manager.execute(query, eng)
        if err:
            self.status_label.setText(f"Failed to load table '{table_name}': {err}")
            return

        self.last_headers = headers or []
        self.last_rows = rows or []

        self.data_view_title.setText(f"📄 <b>{table_name}</b>")
        self.data_view_count.setText(f"· {len(self.last_rows)} record(s) [{eng.upper()}]")
        self.chips_label.setText(f"💡 <b>Quick Actions for `{table_name}`:</b>")

        self._populate_results_grid(self.last_headers, self.last_rows)
        self.results_count_label.setText(f"✓ {len(self.last_rows)} row(s) returned in {elapsed_ms:.2f}ms [{eng.upper()}]")
        self.status_label.setText(f"✓ Displaying '{table_name}' ({len(self.last_rows)} records in {elapsed_ms:.1f}ms). Double-click any cell to edit.")

    def add_new_record(self) -> None:
        """Open AddRecordDialog and insert record directly into the active table."""
        tbl = self._get_active_table_name()
        if not tbl:
            self.status_label.setText("No active table selected. Click a table in the sidebar first.")
            return

        cols_info = self._get_table_columns_info(tbl)
        eng = self.engine_manager.active_engine
        dlg = AddRecordDialog(self, tbl, cols_info, eng)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        record = dlg.get_record_data()
        if not record:
            self.status_label.setText("No data entered. Record was not created.")
            return

        if eng == "nosql":
            self.engine_manager.nosql.insert(tbl, record)
            self.status_label.setText(f"✓ Inserted record into '{tbl}'.")
            self.load_table_data(tbl)
            return

        cols = list(record.keys())
        vals = list(record.values())
        col_str = ", ".join(f"`{c}`" for c in cols)
        val_str = ", ".join(f"'{self._escape_sql(v)}'" for v in vals)
        insert_sql = f"INSERT INTO `{tbl}` ({col_str}) VALUES ({val_str});"

        _, _, affected, _, err = self.engine_manager.execute(insert_sql, eng)
        if err:
            QMessageBox.critical(self, "Insert Error", f"Failed to insert record into '{tbl}':\n{err}")
            self.status_label.setText(f"Insert failed: {err}")
        else:
            self.status_label.setText(f"✓ Successfully added new record to '{tbl}'.")
            self.load_table_data(tbl)

    def delete_selected_records(self) -> None:
        """Delete currently selected row(s) directly from the database table."""
        tbl = self._get_active_table_name()
        if not tbl:
            self.status_label.setText("No active table selected.")
            return

        selected_rows = sorted(list(set(index.row() for index in self.table_widget.selectedIndexes())), reverse=True)
        if not selected_rows and self.table_widget.currentRow() >= 0:
            selected_rows = [self.table_widget.currentRow()]
        if not selected_rows:
            self.status_label.setText("Select a row in the table first, then click Delete Selected.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to permanently delete {len(selected_rows)} record(s) from '{tbl}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        eng = self.engine_manager.active_engine
        if eng == "nosql":
            id_col_idx = None
            for c in range(self.table_widget.columnCount()):
                hdr = self.table_widget.horizontalHeaderItem(c)
                if hdr and hdr.text() == "_id":
                    id_col_idx = c
                    break
            deleted_count = 0
            for r in selected_rows:
                if id_col_idx is not None:
                    id_item = self.table_widget.item(r, id_col_idx)
                    if id_item and id_item.text():
                        deleted_count += self.engine_manager.nosql.delete_by_id(tbl, id_item.text())
            self.status_label.setText(f"✓ Deleted {deleted_count} document(s) from '{tbl}'.")
            self.load_table_data(tbl)
            return

        cols_info = self._get_table_columns_info(tbl)
        pk_col = next((c["name"] for c in cols_info if c.get("is_pk")), None)

        pk_col_idx = None
        if pk_col:
            for c in range(self.table_widget.columnCount()):
                hdr = self.table_widget.horizontalHeaderItem(c)
                if hdr and hdr.text() == pk_col:
                    pk_col_idx = c
                    break

        deleted_count = 0
        for r in selected_rows:
            if pk_col and pk_col_idx is not None:
                pk_val_item = self.table_widget.item(r, pk_col_idx)
                pk_val = pk_val_item.text() if pk_val_item else ""
                del_sql = f"DELETE FROM `{tbl}` WHERE `{pk_col}` = '{self._escape_sql(pk_val)}';"
            else:
                conditions = []
                for c in range(self.table_widget.columnCount()):
                    hdr = self.table_widget.horizontalHeaderItem(c)
                    val_item = self.table_widget.item(r, c)
                    if hdr and val_item is not None:
                        raw_is_null = val_item.data(Qt.ItemDataRole.UserRole) == "__NULL__"
                        if raw_is_null:
                            conditions.append(f"`{hdr.text()}` IS NULL")
                        elif val_item.text() != "":
                            conditions.append(f"`{hdr.text()}` = '{self._escape_sql(val_item.text())}'")
                where_clause = " AND ".join(conditions) if conditions else "1=0"
                del_sql = f"DELETE FROM `{tbl}` WHERE {where_clause};"

            _, _, affected, _, err = self.engine_manager.execute(del_sql, eng)
            if not err and affected:
                deleted_count += affected

        self.status_label.setText(f"✓ Deleted {deleted_count} record(s) from '{tbl}'.")
        self.load_table_data(tbl)

    def _on_table_cell_entered(self, row: int, col: int) -> None:
        """Capture cell value before editing begins for diffing and rollback."""
        item = self.table_widget.item(row, col)
        if item:
            self._cell_pre_edit_value = item.text()
            self._cell_pre_edit_was_null = item.data(Qt.ItemDataRole.UserRole) == "__NULL__"

    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        """TablePlus inline editing: Save cell changes directly to the database."""
        if getattr(self, "_is_populating_grid", False):
            return

        tbl = self._get_active_table_name()
        if not tbl:
            return

        row = item.row()
        col = item.column()
        hdr = self.table_widget.horizontalHeaderItem(col)
        if not hdr:
            return

        col_name = hdr.text()
        new_val = item.text()
        old_val = getattr(self, "_cell_pre_edit_value", "")
        was_null = getattr(self, "_cell_pre_edit_was_null", False)
        if new_val == old_val:
            return

        eng = self.engine_manager.active_engine
        if eng == "nosql":
            if col_name in {"_id", "_created_at"}:
                self._is_populating_grid = True
                item.setText(old_val)
                self._is_populating_grid = False
                return
            id_col_idx = None
            for c in range(self.table_widget.columnCount()):
                h = self.table_widget.horizontalHeaderItem(c)
                if h and h.text() == "_id":
                    id_col_idx = c
                    break
            if id_col_idx is not None:
                id_item = self.table_widget.item(row, id_col_idx)
                if id_item and id_item.text():
                    self.engine_manager.nosql.update_by_id(tbl, id_item.text(), {col_name: new_val})
                    self.status_label.setText(f"✓ Saved NoSQL field `{col_name}` = '{new_val}'.")
                    self._cell_pre_edit_value = new_val
            return

        cols_info = self._get_table_columns_info(tbl)
        pk_col = next((c["name"] for c in cols_info if c.get("is_pk")), None)

        pk_col_idx = None
        if pk_col:
            for c in range(self.table_widget.columnCount()):
                h = self.table_widget.horizontalHeaderItem(c)
                if h and h.text() == pk_col:
                    pk_col_idx = c
                    break

        set_expr = "NULL" if new_val.upper() == "NULL" else f"'{self._escape_sql(new_val)}'"

        if pk_col and pk_col_idx is not None:
            if col == pk_col_idx:
                pk_val = old_val
            else:
                pk_val_item = self.table_widget.item(row, pk_col_idx)
                pk_val = pk_val_item.text() if pk_val_item else ""
            update_sql = f"UPDATE `{tbl}` SET `{col_name}` = {set_expr} WHERE `{pk_col}` = '{self._escape_sql(pk_val)}';"
        else:
            where_cond = f"`{col_name}` IS NULL" if was_null else f"`{col_name}` = '{self._escape_sql(old_val)}'"
            update_sql = f"UPDATE `{tbl}` SET `{col_name}` = {set_expr} WHERE {where_cond};"

        _, _, affected, _, err = self.engine_manager.execute(update_sql, eng)
        if err:
            self.status_label.setText(f"Update failed: {err}")
            self._is_populating_grid = True
            item.setText(old_val)
            self._is_populating_grid = False
            QMessageBox.warning(self, "Update Error", f"Failed to update column '{col_name}':\n{err}")
        else:
            if new_val.upper() == "NULL":
                self._is_populating_grid = True
                item.setText("")
                item.setData(Qt.ItemDataRole.UserRole, "__NULL__")
                self._is_populating_grid = False
            else:
                item.setData(Qt.ItemDataRole.UserRole, None)
            self.status_label.setText(f"✓ Saved change: `{col_name}` = '{new_val}'.")
            self._cell_pre_edit_value = item.text()
            self._cell_pre_edit_was_null = new_val.upper() == "NULL"

    def _action_view_top_data(self) -> None:
        """Dynamic quick action: Select top 50 records from active table."""
        tbl = self._get_active_table_name()
        if not tbl:
            self.status_label.setText("No tables found. Create a table or switch database first.")
            return
        eng = self.engine_manager.active_engine
        if eng == "nosql":
            self.editor.setPlainText(f"db.{tbl}.find();\n")
        else:
            self.editor.setPlainText(f"SELECT * FROM `{tbl}` LIMIT 50;\n")
        self.run_query()

    def _action_count_rows(self) -> None:
        """Dynamic quick action: Count rows in active table."""
        tbl = self._get_active_table_name()
        if not tbl:
            self.status_label.setText("No tables found to count.")
            return
        self.editor.setPlainText(f"SELECT COUNT(*) AS total_rows FROM `{tbl}`;\n")
        self.run_query()

    def _action_describe_table(self) -> None:
        """Dynamic quick action: Show columns and types of active table."""
        tbl = self._get_active_table_name()
        if not tbl:
            self.status_label.setText("No tables found to describe.")
            return
        eng = self.engine_manager.active_engine
        if eng == "mysql":
            self.editor.setPlainText(f"DESCRIBE `{tbl}`;\n")
        else:
            self.editor.setPlainText(f"PRAGMA table_info(`{tbl}`);\n")
        self.run_query()

    def _action_insert_template(self) -> None:
        """Dynamic quick action: Insert valid, type-safe template with real values."""
        tbl = self._get_active_table_name()
        eng = self.engine_manager.active_engine
        cols_metadata = self._get_table_columns_info(tbl or "")

        if not tbl or not cols_metadata:
            self.editor.setPlainText("INSERT INTO new_table (name, status) VALUES ('Sample Item', 'Active');\n")
            self.status_label.setText("Generated generic INSERT template.")
            return

        insert_cols = []
        insert_vals = []
        for col_dict in cols_metadata:
            name = col_dict["name"]
            c_type = col_dict.get("type", "TEXT").upper()
            is_pk = col_dict.get("is_pk", False)
            is_auto = col_dict.get("is_auto", False)

            if is_auto or (is_pk and "INT" in c_type):
                continue

            insert_cols.append(f"`{name}`")

            if any(t in c_type for t in ["INT", "FLOAT", "DECIMAL", "NUMERIC", "DOUBLE", "REAL"]):
                if "age" in name.lower():
                    insert_vals.append("21")
                elif "year" in name.lower():
                    insert_vals.append("2026")
                elif "price" in name.lower() or "cost" in name.lower():
                    insert_vals.append("29.99")
                elif "id" in name.lower():
                    insert_vals.append("1")
                else:
                    insert_vals.append("10")
            elif "BOOL" in c_type:
                insert_vals.append("TRUE")
            elif any(t in c_type for t in ["DATE", "TIME"]):
                insert_vals.append("'2026-01-01'")
            else:
                n_lower = name.lower()
                if "first" in n_lower:
                    insert_vals.append("'Juan'")
                elif "last" in n_lower:
                    insert_vals.append("'Dela Cruz'")
                elif "email" in n_lower:
                    insert_vals.append("'juan@example.com'")
                elif "course" in n_lower or "major" in n_lower:
                    insert_vals.append("'Information Technology'")
                elif "publisher" in n_lower:
                    insert_vals.append("'TechPress Publishing'")
                elif "section" in n_lower:
                    insert_vals.append("'Computer Science'")
                elif "book" in n_lower or "title" in n_lower:
                    insert_vals.append("'Advanced Database Architecture'")
                elif "author" in n_lower:
                    insert_vals.append("'Julian Agustino'")
                else:
                    insert_vals.append(f"'Sample {name}'")

        cols_str = ", ".join(insert_cols)
        vals_str = ", ".join(insert_vals)
        template = f"INSERT INTO `{tbl}` ({cols_str})\nVALUES ({vals_str});\n"
        self.editor.setPlainText(template)
        self.status_label.setText(f"✓ Generated type-safe INSERT template for `{tbl}`. Press [F5] to insert.")

    def _action_create_table_template(self) -> None:
        """Dynamic quick action: Create table template."""
        eng = self.engine_manager.active_engine
        if eng == "mysql":
            self.editor.setPlainText(
                "CREATE TABLE IF NOT EXISTS demo_records (\n"
                "    id INT AUTO_INCREMENT PRIMARY KEY,\n"
                "    title VARCHAR(120) NOT NULL,\n"
                "    category VARCHAR(50) DEFAULT 'General',\n"
                "    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n"
                ");\n"
            )
        else:
            self.editor.setPlainText(
                "CREATE TABLE IF NOT EXISTS demo_records (\n"
                "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
                "    title TEXT NOT NULL,\n"
                "    category TEXT DEFAULT 'General',\n"
                "    created_at DATETIME DEFAULT CURRENT_TIMESTAMP\n"
                ");\n"
            )
        self.status_label.setText("Generated CREATE TABLE template. Press [F5] to execute.")

    def _apply_template(self, sql_template: str, auto_exec: bool) -> None:
        """Load a SQL template and optionally execute it."""
        self.editor.setPlainText(sql_template)
        if auto_exec:
            self.run_query()
        else:
            self.status_label.setText("Loaded SQL template. Edit values or press [F5] to execute.")

    def refresh_history(self) -> None:
        """Update past query history list."""
        self.history_list.clear()
        records = self.engine_manager.load_history(50)
        filter_text = self.history_search.text().strip().lower() if hasattr(self, "history_search") else ""
        for rec in reversed(records):
            status = "✓ OK" if rec.get("status") == "SUCCESS" else "✖ ERR"
            ms = f"{rec.get('elapsed_ms', 0):.1f}ms"
            query = " ".join(rec.get("query", "").split())
            if filter_text and filter_text not in query.lower():
                continue
            item = QListWidgetItem(f"[{status}] {ms:>6}  {query}")
            item.setData(Qt.ItemDataRole.UserRole, rec.get("query", ""))
            if status.startswith("✖"):
                item.setForeground(QColor("#F43F5E"))
            else:
                item.setForeground(QColor("#10B981"))
            self.history_list.addItem(item)

    def _filter_history(self) -> None:
        self.refresh_history()

    def _clear_history(self) -> None:
        if hasattr(self.engine_manager, "_history_file") and self.engine_manager._history_file.exists():
            self.engine_manager._history_file.unlink()
        self.refresh_history()
        self.status_label.setText("Query history cleared.")

    def _on_history_item_double_clicked(self, item: QListWidgetItem) -> None:
        raw_query = item.data(Qt.ItemDataRole.UserRole)
        if raw_query:
            self.switch_to_sql_view()
            self.editor.setPlainText(raw_query + ("\n" if not raw_query.endswith("\n") else ""))
            self.status_label.setText("Loaded selected query from history into Code Editor.")

    def _on_schema_item_clicked(self, item: QTreeWidgetItem, _: int) -> None:
        """TablePlus single click: Immediately switch to Data Browser and load table data."""
        data = item.data(0, Qt.ItemDataRole.UserRole) or ""
        parts = data.split(":")
        kind = parts[0]

        if kind == "table":
            db_name = parts[1] if len(parts) > 2 else ""
            tbl_name = parts[2] if len(parts) > 2 else parts[1]

            if self.engine_manager.active_engine == "mysql" and db_name and db_name != self.settings.database:
                try:
                    self.mysql.connect(db_name)
                    self.settings.database = db_name
                    self.database_combo.blockSignals(True)
                    self.database_combo.setCurrentText(db_name)
                    self.database_combo.blockSignals(False)
                    self.engine_indicator.setText(f"Engine: MYSQL ({db_name})")
                except Exception:
                    pass

            self.switch_to_data_view()
            self.load_table_data(tbl_name)
        elif kind == "db":
            db_name = parts[1]
            if self.engine_manager.active_engine == "mysql":
                self.database_combo.setCurrentText(db_name)
        elif kind == "col":
            col_name = parts[1]
            col_type = parts[2] if len(parts) > 2 else "TEXT"
            self.status_label.setText(f"Column: `{col_name}` [{col_type}]. Right-click to copy.")

    def _on_schema_item_double_clicked(self, item: QTreeWidgetItem, _: int) -> None:
        """Double click opens table data in Data Browser. Columns NEVER touch editor."""
        data = item.data(0, Qt.ItemDataRole.UserRole) or ""
        parts = data.split(":")
        kind = parts[0]

        if kind == "col":
            col_name = parts[1]
            self.status_label.setText(f"Column `{col_name}` selected. Right-click to copy.")
            return

        if kind == "db":
            db_name = parts[1]
            if self.engine_manager.active_engine == "mysql":
                self.database_combo.setCurrentText(db_name)
            return

        if kind == "table":
            db_name = parts[1] if len(parts) > 2 else ""
            table_name = parts[2] if len(parts) > 2 else parts[1]
            if self.engine_manager.active_engine == "mysql" and db_name and db_name != self.settings.database:
                self.database_combo.setCurrentText(db_name)
            self.switch_to_data_view()
            self.load_table_data(table_name)

    def _show_schema_context_menu(self, pos: QPoint) -> None:
        item = self.schema_tree.itemAt(pos)
        if not item:
            menu = QMenu(self)
            act_new_tbl = menu.addAction("✨ Create New Table...")
            act_new_db = menu.addAction("➕ Create New Database...")
            menu.addSeparator()
            act_ref = menu.addAction("🔄 Refresh Schema")
            chosen = menu.exec(self.schema_tree.mapToGlobal(pos))
            if chosen == act_new_tbl:
                self.prompt_create_table()
            elif chosen == act_new_db:
                self.prompt_create_database()
            elif chosen == act_ref:
                self.refresh_schema()
            return

        if not item.data(0, Qt.ItemDataRole.UserRole):
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)
        parts = data.split(":")
        kind = parts[0]

        menu = QMenu(self)

        if kind == "col":
            col_name = parts[1]
            act_copy_col = menu.addAction(f"📋 Copy Column `{col_name}`")
            act_insert_col = menu.addAction(f"➕ Insert `{col_name}` into Editor")
            chosen = menu.exec(self.schema_tree.mapToGlobal(pos))
            if chosen == act_copy_col:
                QApplication.clipboard().setText(col_name)
                self.status_label.setText(f"Copied `{col_name}` to clipboard.")
            elif chosen == act_insert_col:
                self.editor.textCursor().insertText(f" `{col_name}` ")
                self.status_label.setText(f"Inserted `{col_name}` into editor.")
            return

        if kind == "db":
            db_name = parts[1]
            act_switch_db = menu.addAction(f"📁 Switch to `{db_name}`")
            act_new_table = menu.addAction(f"✨ Create New Table in `{db_name}`...")
            act_new_db = menu.addAction("➕ Create New Database...")
            act_copy_name = menu.addAction(f"📋 Copy Database Name")
            menu.addSeparator()
            act_drop_db = menu.addAction(f"🗑️ Drop Database `{db_name}`...")

            chosen = menu.exec(self.schema_tree.mapToGlobal(pos))
            if chosen == act_switch_db:
                self.database_combo.setCurrentText(db_name)
            elif chosen == act_new_table:
                self.prompt_create_table(target_db=db_name)
            elif chosen == act_new_db:
                self.prompt_create_database()
            elif chosen == act_copy_name:
                QApplication.clipboard().setText(db_name)
                self.status_label.setText(f"Copied `{db_name}` to clipboard.")
            elif chosen == act_drop_db:
                self.prompt_drop_database(db_name)
            return

        if kind != "table":
            return

        db_name = parts[1] if len(parts) > 2 else ""
        table_name = parts[2] if len(parts) > 2 else parts[1]

        act_open_view = menu.addAction(f"📊 Open in Data Browser")
        act_query = menu.addAction(f"▶ Select Top 50 in Editor")
        act_count = menu.addAction(f"🔢 Count Rows in `{table_name}`")
        act_desc = menu.addAction(f"📋 Describe Structure")
        act_copy = menu.addAction("📋 Copy Table Name")
        act_new_table = menu.addAction("✨ Create Another Table...")
        menu.addSeparator()
        act_drop = menu.addAction("🗑️ Drop Table...")

        chosen = menu.exec(self.schema_tree.mapToGlobal(pos))
        if chosen == act_open_view:
            if db_name and self.engine_manager.active_engine == "mysql":
                self.database_combo.setCurrentText(db_name)
            self.switch_to_data_view()
            self.load_table_data(table_name)
        elif chosen == act_query:
            if db_name and self.engine_manager.active_engine == "mysql":
                self.database_combo.setCurrentText(db_name)
            self.active_table_name = table_name
            self.switch_to_sql_view()
            self.editor.setPlainText(f"SELECT * FROM `{table_name}` LIMIT 50;\n")
            self.run_query()
        elif chosen == act_count:
            self.switch_to_sql_view()
            self.editor.setPlainText(f"SELECT COUNT(*) AS total_rows FROM `{table_name}`;\n")
            self.run_query()
        elif chosen == act_desc:
            self.switch_to_sql_view()
            if self.engine_manager.active_engine == "mysql":
                self.editor.setPlainText(f"DESCRIBE `{table_name}`;\n")
            else:
                self.editor.setPlainText(f"PRAGMA table_info(`{table_name}`);\n")
            self.run_query()
        elif chosen == act_copy:
            QApplication.clipboard().setText(table_name)
            self.status_label.setText(f"Copied `{table_name}` to clipboard.")
        elif chosen == act_new_table:
            self.prompt_create_table(target_db=db_name)
        elif chosen == act_drop:
            confirm = QMessageBox.question(
                self,
                "Confirm Drop Table",
                f"Are you sure you want to drop table '{table_name}'?\nAll data in this table will be lost.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self.switch_to_sql_view()
                self.editor.setPlainText(f"DROP TABLE IF EXISTS `{table_name}`;\n")
                self.run_query()

    def _show_table_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        act_cell = menu.addAction("📋 Copy Selected Cell")
        act_row = menu.addAction("📋 Copy Selected Row")
        act_table = menu.addAction("📊 Copy Entire Table (TSV)")
        menu.addSeparator()
        act_add = menu.addAction("➕ Add New Record...")
        act_del = menu.addAction("🗑️ Delete Selected Record(s)")
        menu.addSeparator()
        act_csv = menu.addAction("📤 Export to CSV...")
        act_json = menu.addAction("📤 Export to JSON...")

        chosen = menu.exec(self.table_widget.mapToGlobal(pos))
        current_item = self.table_widget.currentItem()

        if chosen == act_cell and current_item:
            QApplication.clipboard().setText(current_item.text())
            self.status_label.setText("Copied cell value to clipboard.")
        elif chosen == act_row and current_item:
            r = current_item.row()
            row_vals = [
                self.table_widget.item(r, c).text() if self.table_widget.item(r, c) else ""
                for c in range(self.table_widget.columnCount())
            ]
            QApplication.clipboard().setText("\t".join(row_vals))
            self.status_label.setText(f"Copied row {r + 1} to clipboard.")
        elif chosen == act_table:
            self._copy_entire_table_tsv()
        elif chosen == act_add:
            self.add_new_record()
        elif chosen == act_del:
            self.delete_selected_records()
        elif chosen == act_csv:
            self.export_csv()
        elif chosen == act_json:
            self.export_json()

    def _copy_entire_table_tsv(self) -> None:
        if not self.last_headers or not self.last_rows:
            self.status_label.setText("No query results to copy.")
            return
        lines = ["\t".join(self.last_headers)]
        for row in self.last_rows:
            lines.append("\t".join("" if v is None else str(v) for v in row))
        tsv_text = "\n".join(lines)
        QApplication.clipboard().setText(tsv_text)
        self.status_label.setText(f"✓ Copied {len(self.last_rows)} row(s) to clipboard as TSV.")

    def _filter_schema_tree(self, text: str) -> None:
        """Filter schema tree items in real-time as user types."""
        query = text.strip().lower()
        for i in range(self.schema_tree.topLevelItemCount()):
            top_item = self.schema_tree.topLevelItem(i)
            if not top_item:
                continue
            if not query:
                top_item.setHidden(False)
                for j in range(top_item.childCount()):
                    tbl_item = top_item.child(j)
                    if tbl_item:
                        tbl_item.setHidden(False)
                        for k in range(tbl_item.childCount()):
                            col_item = tbl_item.child(k)
                            if col_item:
                                col_item.setHidden(False)
                continue

            top_match = query in top_item.text(0).lower()
            any_table_matched = False

            for j in range(top_item.childCount()):
                tbl_item = top_item.child(j)
                if not tbl_item:
                    continue
                tbl_match = query in tbl_item.text(0).lower()
                any_col_matched = False

                for k in range(tbl_item.childCount()):
                    col_item = tbl_item.child(k)
                    if not col_item:
                        continue
                    col_match = query in col_item.text(0).lower()
                    col_item.setHidden(not (col_match or tbl_match or top_match))
                    if col_match:
                        any_col_matched = True

                tbl_item.setHidden(not (tbl_match or any_col_matched or top_match))
                if tbl_match or any_col_matched:
                    any_table_matched = True
                    tbl_item.setExpanded(True)

            top_item.setHidden(not (top_match or any_table_matched))
            if any_table_matched:
                top_item.setExpanded(True)

    def _filter_results_table(self, text: str) -> None:
        """Filter table rows in real-time as user types in search box."""
        query = text.strip().lower()
        grids = [self.table_widget]
        if hasattr(self, "query_table_widget"):
            grids.append(self.query_table_widget)

        visible_count = 0
        total = self.table_widget.rowCount()
        for grid in grids:
            g_total = grid.rowCount()
            for r in range(g_total):
                if not query:
                    grid.setRowHidden(r, False)
                    if grid is self.table_widget:
                        visible_count += 1
                    continue
                matched = False
                for c in range(grid.columnCount()):
                    item = grid.item(r, c)
                    if item and query in item.text().lower():
                        matched = True
                        break
                grid.setRowHidden(r, not matched)
                if matched and grid is self.table_widget:
                    visible_count += 1

        if query:
            self.results_count_label.setText(f"Displaying {visible_count} of {total} row(s) (filtered)")
        else:
            if self.last_rows is not None:
                self.results_count_label.setText(f"✓ {len(self.last_rows)} row(s)")

    def _populate_tutor_topics(self, category: str = "", query: str = "", difficulty: str = "") -> None:
        """Populate the topic combobox based on active search, category, and difficulty filters."""
        if not hasattr(self, "topic_combo"):
            return
        self.topic_combo.blockSignals(True)
        self.topic_combo.clear()

        matches = filter_topics(category=category, query=query, difficulty=difficulty)
        for t in matches:
            label = f"{t.name} ({t.category})"
            self.topic_combo.addItem(label, userData=t.key)

        self.topic_combo.blockSignals(False)
        if self.topic_combo.count() > 0:
            self.topic_combo.setCurrentIndex(0)
            self._on_tutor_topic_changed(0)
        else:
            self._clear_tutor_display()
        self._update_tutor_stats()

    def _on_tutor_filter_changed(self) -> None:
        """Handler for changes in tutor search bar or filter dropdowns."""
        q = self.tutor_search.text().strip()
        cat = self.tutor_cat_combo.currentText().strip()
        diff = self.tutor_diff_combo.currentText().strip()
        self._populate_tutor_topics(category=cat, query=q, difficulty=diff)

    def _clear_tutor_display(self) -> None:
        """Clear tutor detail views when search filters yield zero results."""
        self.tutor_title.setText("No Matching Topics")
        self.tutor_category_chip.setText("NONE")
        self.tutor_difficulty_chip.setText("N/A")
        self.tutor_summary.setText("No topics match your current filter criteria. Clear search or reset filters.")
        self.tutor_syntax.setPlainText("")
        self.tutor_example.setPlainText("")
        self.tutor_notes.setText("")
        self.tutor_challenge_desc.setText("")
        self.tutor_count_label.setText("0 topics found")

    def _update_tutor_stats(self) -> None:
        """Update header metrics for topic position and session mastery count."""
        total = self.topic_combo.count()
        cur = self.topic_combo.currentIndex() + 1 if total > 0 else 0
        mastered_count = len(self.mastered_topics)
        self.tutor_count_label.setText(f"Topic {cur}/{total} • {mastered_count} Mastered")

    def _toggle_topic_mastered(self) -> None:
        """Toggle mastered state for the currently viewed topic."""
        key = self.topic_combo.currentData() or self.topic_combo.currentText()
        if not key:
            return
        topic = lookup_topic(key)
        if not topic:
            return
        if self.tutor_mark_done_check.isChecked():
            self.mastered_topics.add(topic.key)
        else:
            self.mastered_topics.discard(topic.key)
        self._update_tutor_stats()

    def _prev_tutor_topic(self) -> None:
        """Navigate to the previous topic in the filtered list."""
        cur = self.topic_combo.currentIndex()
        if cur > 0:
            self.topic_combo.setCurrentIndex(cur - 1)

    def _next_tutor_topic(self) -> None:
        """Navigate to the next topic in the filtered list."""
        cur = self.topic_combo.currentIndex()
        if cur < self.topic_combo.count() - 1:
            self.topic_combo.setCurrentIndex(cur + 1)

    def _on_tutor_topic_changed(self, _: int = 0) -> None:
        """Update topic detail view cards when selected topic changes."""
        if not hasattr(self, "topic_combo") or self.topic_combo.count() == 0:
            return
        key = self.topic_combo.currentData() or self.topic_combo.currentText()
        topic = lookup_topic(key)
        if not topic:
            return

        self.tutor_title.setText(topic.name)
        self.tutor_category_chip.setText(topic.category.upper())

        diff = topic.difficulty or "Beginner"
        if diff.lower() == "beginner":
            self.tutor_difficulty_chip.setText("🟢 BEGINNER")
            self.tutor_difficulty_chip.setStyleSheet("background: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 3px; padding: 1px 5px; font-weight: bold; font-size: 7.5pt;")
        elif diff.lower() == "intermediate":
            self.tutor_difficulty_chip.setText("🟡 INTERMEDIATE")
            self.tutor_difficulty_chip.setStyleSheet("background: rgba(245, 158, 11, 0.15); color: #F59E0B; border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 3px; padding: 1px 5px; font-weight: bold; font-size: 7.5pt;")
        else:
            self.tutor_difficulty_chip.setText("🔴 ADVANCED")
            self.tutor_difficulty_chip.setStyleSheet("background: rgba(244, 63, 94, 0.15); color: #F43F5E; border: 1px solid rgba(244, 63, 94, 0.3); border-radius: 3px; padding: 1px 5px; font-weight: bold; font-size: 7.5pt;")

        self.tutor_summary.setText(f"<b>{topic.name}</b> ({topic.category})<br><br>{topic.summary}")
        self.tutor_syntax.setPlainText(topic.syntax)
        self.tutor_example.setPlainText(topic.example)

        notes_text = topic.notes or "Always verify syntax against your active engine and schema."
        self.tutor_notes.setText(notes_text)

        prompt, _ = get_topic_challenge(topic)
        self.tutor_challenge_desc.setText(prompt)

        self.tutor_mark_done_check.blockSignals(True)
        self.tutor_mark_done_check.setChecked(topic.key in self.mastered_topics)
        self.tutor_mark_done_check.blockSignals(False)

        self._update_tutor_stats()

    def _copy_tutor_syntax(self) -> None:
        """Copy syntax blueprint to clipboard."""
        text = self.tutor_syntax.toPlainText().strip()
        if text:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
                self.status_label.setText("📋 Copied syntax blueprint to clipboard.")

    def _copy_tutor_example(self) -> None:
        """Copy example query to clipboard."""
        text = self.tutor_example.toPlainText().strip()
        if text:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
                self.status_label.setText("📋 Copied example query to clipboard.")

    def _load_tutor_example_into_editor(self) -> None:
        """Load topic example query into the SQL editor."""
        example = self.tutor_example.toPlainText().strip()
        if example:
            self.switch_to_sql_view()
            self.editor.setPlainText(example + "\n")
            self.status_label.setText("Loaded example into editor. Press [F5] to run.")

    def _run_tutor_example_live(self) -> None:
        """Load example query and immediately execute it against the live database."""
        example = self.tutor_example.toPlainText().strip()
        if example:
            self.switch_to_sql_view()
            self.editor.setPlainText(example + "\n")
            self.run_query()
            self.status_label.setText("✓ Executing SQL Tutor query live against database.")

    def _adapt_tutor_example_to_active_table(self) -> None:
        """Intelligently adapt generic example query to use real columns from the active table."""
        example = self.tutor_example.toPlainText().strip()
        if not example:
            return
        tbl = self._get_active_table_name()
        if not tbl:
            self.status_label.setText("⚠️ Select a table from Schema Tree or click [Seed Demo Data] to adapt query.")
            return

        cols_info = self._get_table_columns_info(tbl)
        cols = [c["name"] for c in cols_info if "name" in c] if cols_info else ["id", "name"]
        adapted = adapt_query_to_schema(example, tbl, cols)
        self.switch_to_sql_view()
        self.editor.setPlainText(adapted + "\n")
        self.status_label.setText(f"✓ Adapted query to active table `{tbl}` ({len(cols)} column(s)). Press [F5] to run.")

    def _load_challenge_into_editor(self) -> None:
        """Load an interactive mission and practice skeleton into the SQL editor."""
        key = self.topic_combo.currentData() or self.topic_combo.currentText()
        topic = lookup_topic(key)
        if not topic:
            return
        prompt, _ = get_topic_challenge(topic)
        tbl = self._get_active_table_name() or "your_table"
        mission = (
            f"-- ========================================================\n"
            f"-- 🎯 SQL TUTOR MISSION: {topic.name}\n"
            f"-- Category: {topic.category}  |  Difficulty: {topic.difficulty}\n"
            f"-- Objective: {prompt}\n"
            f"-- Target Table: `{tbl}`\n"
            f"-- ========================================================\n\n"
            f"-- TODO: Formulate your query solution below and press [F5] to run:\n"
            f"SELECT * FROM `{tbl}` LIMIT 10;\n"
        )
        self.switch_to_sql_view()
        self.editor.setPlainText(mission)
        self.status_label.setText(f"🎯 Mission loaded for '{topic.name}'. Complete query and press [F5].")

    def _show_tutor_solution(self) -> None:
        """Reveal solution query for the current topic challenge."""
        key = self.topic_combo.currentData() or self.topic_combo.currentText()
        topic = lookup_topic(key)
        if not topic:
            return
        _, solution = get_topic_challenge(topic)
        self.switch_to_sql_view()
        self.editor.setPlainText(f"-- 💡 Solution for {topic.name}:\n{solution}\n")
        self.status_label.setText(f"💡 Solution loaded into editor. Press [F5] to run.")

    def _open_tutorial_for_error(self) -> None:
        """Switch to SQL tutor tab and display guidance matching the diagnosed error."""
        if not self.last_diagnostic:
            return
        diag_rule = (self.last_diagnostic.rule_tip or "").lower()
        err_type = (self.last_diagnostic.error_type or "").lower()
        target_idx = -1
        for i in range(self.topic_combo.count()):
            key = (self.topic_combo.itemData(i) or "").lower()
            topic_name = self.topic_combo.itemText(i).lower()
            if key and (key in diag_rule or key in err_type):
                target_idx = i
                break
            for word in topic_name.split():
                clean_w = word.strip("(),.-").lower()
                if len(clean_w) >= 4 and (clean_w in diag_rule or clean_w in err_type):
                    target_idx = i
                    break
            if target_idx >= 0:
                break

        if target_idx >= 0:
            self.topic_combo.setCurrentIndex(target_idx)
        self.sidebar_tabs.setCurrentIndex(2)
        self.status_label.setText("Opened SQL Tutor tutorial for this SQL error.")

    def seed_demo_data(self) -> None:
        """Seed sample demo data (used for test suite or empty environments)."""
        eng = self.engine_manager.active_engine
        msg = self.engine_manager.load_sample_data(eng)
        self.refresh_schema()
        self.active_table_name = "students"
        self.editor.setPlainText("SELECT * FROM students ORDER BY gpa DESC;\n")
        self.run_query()
        self.status_label.setText(f"✓ {msg}")

    def run_query(self) -> None:
        """Execute query with real-time UI synchronization and instant mutation view refresh."""
        # Ensure we are in SQL Console mode so user and diagnostics HUD are visible
        self.switch_to_sql_view()

        sql = self.editor.toPlainText().strip()
        if not sql:
            self.status_label.setText("Code editor is empty. Enter a query first.")
            return

        # Track active table from SELECT statements as well
        select_table_match = re.search(r"\bFROM\s+[`\"]?([a-zA-Z0-9_$]+)[`\"]?", sql, re.IGNORECASE)
        if select_table_match:
            self.active_table_name = select_table_match.group(1)

        eng = self.engine_manager.active_engine
        headers, rows, count, elapsed_ms, err = self.engine_manager.execute(sql, eng)

        if err:
            schema = self.engine_manager.get_schema(eng)
            diag = analyze_error(sql, err, schema, engine=eng)
            self.last_diagnostic = diag

            # Show Error HUD
            self.error_title.setText(f"✖ {diag.error_type} (Error Code: {diag.error_code or 'N/A'})")
            self.error_problem.setText(f"Problem: {diag.plain_summary or diag.message}")
            self.error_why.setText(f"Why it failed: {diag.why_failed or diag.explanation}")
            self.error_rule.setText(f"Rule: {diag.rule_tip or 'Check W3Schools tutorial'}")
            self.error_frame.setVisible(True)

            self.auto_fix_btn.setEnabled(diag.corrected_sql is not None or diag.suggested_fix is not None)
            self.hud_fix_btn.setEnabled(self.auto_fix_btn.isEnabled())

            self.status_label.setText(f"Execution failed ({elapsed_ms:.1f}ms). Check Error HUD above.")
        else:
            self.last_diagnostic = None
            self.error_frame.setVisible(False)
            self.auto_fix_btn.setEnabled(False)

            # Check if this was a mutation query (INSERT, UPDATE, DELETE)
            mutation_match = re.search(
                r"\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|REPLACE\s+INTO)\s+[`\"]?([a-zA-Z0-9_$]+)[`\"]?",
                sql,
                re.IGNORECASE,
            )

            if mutation_match and count is not None:
                target_table = mutation_match.group(1)
                self.active_table_name = target_table

                preview_headers, preview_rows, preview_count, _, _ = self.engine_manager.execute(
                    f"SELECT * FROM `{target_table}` LIMIT 250;", eng
                )

                if preview_headers and preview_rows is not None:
                    self.last_headers = preview_headers
                    self.last_rows = preview_rows
                    self._populate_results_grid(preview_headers, preview_rows)
                    self.data_view_title.setText(f"📄 <b>{target_table}</b>")
                    self.data_view_count.setText(f"· {len(preview_rows)} record(s) [{eng.upper()}]")
                    self.results_count_label.setText(f"✓ {count} affected. Showing `{target_table}` ({len(preview_rows)} rows) [{eng.upper()}]")
                    self.status_label.setText(f"✓ Statement succeeded ({count} affected). Real-time grid refreshed for `{target_table}`.")
                else:
                    self._populate_summary_grid(f"Statement executed successfully. {count} row(s) affected.")
                    self.results_count_label.setText(f"✓ {count} row(s) affected in {elapsed_ms:.2f}ms [{eng.upper()}]")
                    self.status_label.setText(f"Statement executed successfully ({count} affected).")
            elif headers and rows is not None:
                self.last_headers = headers
                self.last_rows = rows
                self._populate_results_grid(headers, rows)
                self.results_count_label.setText(f"✓ {len(rows)} row(s) returned in {elapsed_ms:.2f}ms [{eng.upper()}]")
                self.status_label.setText(f"Query executed cleanly in {elapsed_ms:.2f}ms. Displaying {len(rows)} row(s).")
            else:
                self._populate_summary_grid(f"Statement executed successfully. {count} row(s) affected.")
                self.results_count_label.setText(f"✓ {count} row(s) affected in {elapsed_ms:.2f}ms [{eng.upper()}]")
                self.status_label.setText(f"Statement executed successfully ({count} affected).")

        self.table_filter_input.clear()
        self.refresh_history()

        # Check if query switched database or altered tables in real time
        use_match = re.search(r"\bUSE\s+[`\"]?([a-zA-Z0-9_$]+)[`\"]?", sql, re.IGNORECASE)
        if use_match and not err and eng == "mysql":
            switched_db = use_match.group(1)
            self.settings.database = switched_db
            self.database_combo.blockSignals(True)
            self.database_combo.setCurrentText(switched_db)
            self.database_combo.blockSignals(False)
            self.engine_indicator.setText(f"Engine: MYSQL ({switched_db})")

        if re.search(r"\b(USE|CREATE|DROP|ALTER)\b", sql, re.IGNORECASE) and not err:
            self._sync_databases_dropdown()
            self.refresh_schema()

    def _populate_results_grid(self, headers: list[str], rows: list[tuple]) -> None:
        """Populate spreadsheet grid with rows and center/right-align numeric columns."""
        self._is_populating_grid = True
        self.table_widget.setSortingEnabled(False)
        self.table_widget.blockSignals(True)
        if hasattr(self, "query_table_widget"):
            self.query_table_widget.setSortingEnabled(False)
            self.query_table_widget.blockSignals(True)

        # Populate primary data table widget
        self.table_widget.setColumnCount(len(headers))
        self.table_widget.setRowCount(len(rows))
        self.table_widget.setHorizontalHeaderLabels(headers)

        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                display_text = "" if val is None else str(val)
                item = QTableWidgetItem(display_text)
                if val is None:
                    item.setData(Qt.ItemDataRole.UserRole, "__NULL__")
                if isinstance(val, (int, float)):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table_widget.setItem(r_idx, c_idx, item)

        self.table_widget.resizeColumnsToContents()
        self.table_widget.setSortingEnabled(True)
        self.table_widget.blockSignals(False)

        # Also populate query table widget if present
        if hasattr(self, "query_table_widget"):
            self.query_table_widget.setColumnCount(len(headers))
            self.query_table_widget.setRowCount(len(rows))
            self.query_table_widget.setHorizontalHeaderLabels(headers)
            for r_idx, row in enumerate(rows):
                for c_idx, val in enumerate(row):
                    display_text = "" if val is None else str(val)
                    item = QTableWidgetItem(display_text)
                    if val is None:
                        item.setData(Qt.ItemDataRole.UserRole, "__NULL__")
                    if isinstance(val, (int, float)):
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.query_table_widget.setItem(r_idx, c_idx, item)
            self.query_table_widget.resizeColumnsToContents()
            self.query_table_widget.setSortingEnabled(True)
            self.query_table_widget.blockSignals(False)

        self._is_populating_grid = False

    def _populate_summary_grid(self, message: str) -> None:
        self._is_populating_grid = True
        self.table_widget.setSortingEnabled(False)
        self.table_widget.blockSignals(True)
        self.table_widget.setColumnCount(1)
        self.table_widget.setRowCount(1)
        self.table_widget.setHorizontalHeaderLabels(["Execution Summary"])
        self.table_widget.setItem(0, 0, QTableWidgetItem(message))
        self.table_widget.blockSignals(False)

        if hasattr(self, "query_table_widget"):
            self.query_table_widget.setSortingEnabled(False)
            self.query_table_widget.blockSignals(True)
            self.query_table_widget.setColumnCount(1)
            self.query_table_widget.setRowCount(1)
            self.query_table_widget.setHorizontalHeaderLabels(["Execution Summary"])
            self.query_table_widget.setItem(0, 0, QTableWidgetItem(message))
            self.query_table_widget.blockSignals(False)

        self._is_populating_grid = False

    def apply_auto_fix(self) -> None:
        """Apply suggested auto-fix to editor and rerun query."""
        if not self.last_diagnostic:
            return

        diag = self.last_diagnostic
        if diag.corrected_sql:
            self.editor.setPlainText(diag.corrected_sql)
            self.status_label.setText("✓ Auto-fix applied! Re-running query...")
            self.run_query()
            return

        if diag.suggested_fix:
            sql = self.editor.toPlainText()
            match = re.search(r"replace '([^']+)' with '([^']+)'", diag.suggested_fix, re.IGNORECASE)
            if match:
                old_tok, new_tok = match.group(1), match.group(2)
                sql = re.sub(r"\b" + re.escape(old_tok) + r"\b", new_tok, sql, flags=re.IGNORECASE)
                self.editor.setPlainText(sql)
                self.status_label.setText(f"✓ Replaced '{old_tok}' with '{new_tok}'. Re-running...")
                self.run_query()
                return

    def run_autopilot(self) -> None:
        """Generate SQL query from natural language goal and execute."""
        goal = self.autopilot_input.text().strip()
        if not goal:
            return
        eng = self.engine_manager.active_engine
        db_ctx = self.mysql if eng == "mysql" else self.engine_manager.get_schema(eng)
        sql, cat, exp = generate_autopilot_plan(
            goal,
            db_ctx,
            self.settings,
            engine=eng,
        )
        self.editor.setPlainText(sql + "\n")
        self.autopilot_input.clear()
        self.status_label.setText(f"✈ Autopilot ({cat}): {exp}")
        self.run_query()

    def format_sql(self) -> None:
        """Format and uppercase SQL keywords in Code Editor."""
        sql = self.editor.toPlainText()
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
        self.editor.setPlainText(formatted)
        self.status_label.setText("✓ Formatted SQL keywords to uppercase.")

    def prompt_create_table(self, target_db: str | None = None) -> None:
        """Open visual Create Table Wizard and execute table creation."""
        eng = self.engine_manager.active_engine
        active_db = target_db or (self.settings.database if eng == "mysql" else "workspace")

        if hasattr(self, "health_timer"):
            self.health_timer.stop()
        try:
            dlg = CreateTableDialog(self, target_db=active_db)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return

            table_name, sql = dlg.get_create_table_sql(eng)
            if not table_name or not sql:
                return

            _, _, _, _, err = self.engine_manager.execute(sql, eng)
            if err:
                QMessageBox.critical(self, "Create Table Error", f"Failed to create table '{table_name}':\n{err}")
                return

            self.refresh_schema()
            self.active_table_name = table_name
            self.switch_to_data_view()
            self.load_table_data(table_name)
            self.status_label.setText(f"✓ Created table `{table_name}` successfully! Ready to add records.")
        finally:
            if hasattr(self, "health_timer"):
                self.health_timer.start()

    def prompt_create_database(self) -> None:
        """Prompt user to create a new database."""
        eng = self.engine_manager.active_engine
        if eng != "mysql":
            QMessageBox.information(
                self,
                "Create Database",
                f"Databases are managed automatically in {eng.upper()} mode.\n"
                f"Use 'CREATE TABLE ...' or 'db.<collection>.insert()' directly."
            )
            return

        db_name, ok = QInputDialog.getText(
            self,
            "Create New Database",
            "Enter new database name (alphanumeric and underscores only):",
        )
        if not ok or not db_name.strip():
            return

        clean_name = re.sub(r"[^\w$]", "_", db_name.strip())
        sql = f"CREATE DATABASE IF NOT EXISTS `{clean_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        _, _, _, _, err = self.engine_manager.execute(sql, "mysql")
        if err:
            QMessageBox.critical(self, "Create Database Error", f"Failed to create database '{clean_name}':\n{err}")
            return

        self.settings.database = clean_name
        self._sync_databases_dropdown()
        self.refresh_schema()
        self.status_label.setText(f"✓ Created and switched to database '{clean_name}'.")

    def prompt_drop_database(self, db_name: str | None = None) -> None:
        """Prompt user with safety confirmation to permanently DROP a database."""
        eng = self.engine_manager.active_engine
        if eng != "mysql":
            QMessageBox.information(
                self,
                "Drop Database",
                f"In {eng.upper()} mode, data is stored in the workspace file.\n"
                f"To drop a table, right-click any table and choose 'Drop Table'."
            )
            return

        target_db = db_name or self.database_combo.currentText().strip()
        if not target_db or target_db.startswith("("):
            QMessageBox.warning(self, "No Database Selected", "Please select a database to drop.")
            return

        # System database protection
        system_dbs = {"information_schema", "performance_schema", "mysql", "sys", "phpmyadmin"}
        if target_db.lower() in system_dbs:
            QMessageBox.critical(
                self,
                "Protected System Database",
                f"Cannot drop MySQL system database '{target_db}'."
            )
            return

        confirm = QMessageBox.warning(
            self,
            "⚠️ Confirm DROP DATABASE",
            f"Are you ABSOLUTELY sure you want to permanently delete database '{target_db}'?\n\n"
            f"⚠️ ALL tables, columns, and records in '{target_db}' will be permanently deleted.\n"
            f"This action CANNOT be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        sql = f"DROP DATABASE IF EXISTS `{target_db}`;"
        _, _, _, _, err = self.engine_manager.execute(sql, "mysql")
        if err:
            QMessageBox.critical(self, "Drop Database Error", f"Failed to drop database '{target_db}':\n{err}")
            return

        if self.settings.database == target_db:
            remaining_dbs = self.engine_manager.get_mysql_databases()
            self.settings.database = remaining_dbs[0] if remaining_dbs else ""

        self._sync_databases_dropdown()
        self.refresh_schema()
        self.status_label.setText(f"✓ Database '{target_db}' has been dropped.")
        QMessageBox.information(self, "Database Dropped", f"Database '{target_db}' was deleted successfully.")

    def export_csv(self) -> None:
        """Export current results table to CSV."""
        if not self.last_headers or not self.last_rows:
            QMessageBox.information(self, "Export CSV", "No query results to export. Run a query that returns rows first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export Results to CSV", "results.csv", "CSV Files (*.csv)")
        if file_path:
            try:
                with open(file_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(self.last_headers)
                    writer.writerows(self.last_rows)
                self.status_label.setText(f"✓ Exported {len(self.last_rows)} row(s) to '{file_path}'")
                QMessageBox.information(self, "Export Successful", f"Saved {len(self.last_rows)} row(s) to:\n{file_path}")
            except Exception as exc:
                QMessageBox.critical(self, "Export Error", f"Failed to save CSV file:\n{exc}")

    def export_json(self) -> None:
        """Export current results table to JSON."""
        if not self.last_headers or not self.last_rows:
            QMessageBox.information(self, "Export JSON", "No query results to export. Run a query that returns rows first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export Results to JSON", "results.json", "JSON Files (*.json)")
        if file_path:
            try:
                data = [dict(zip(self.last_headers, row)) for row in self.last_rows]
                Path(file_path).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
                self.status_label.setText(f"✓ Exported {len(self.last_rows)} row(s) to '{file_path}'")
                QMessageBox.information(self, "Export Successful", f"Saved {len(self.last_rows)} row(s) to:\n{file_path}")
            except Exception as exc:
                QMessageBox.critical(self, "Export Error", f"Failed to save JSON file:\n{exc}")


def start_gui_app(
    engine_manager: MultiEngineManager,
    settings: Settings,
    mysql_db: Database,
) -> None:
    """Launch the native PyQt6 Desktop Studio application."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.DisableProcessWindowsGhosting()
        except Exception:
            pass
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = SQLStudioWindow(engine_manager, settings, mysql_db)
    window.show()
    app.exec()
