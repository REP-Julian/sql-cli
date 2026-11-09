"""Intelligent inline ghost autosuggestion for SQL statements and commands."""

from __future__ import annotations

import re
from typing import Any

from prompt_toolkit.auto_suggest import AutoSuggest, AutoSuggestFromHistory, Suggestion
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document


class SQLAutoSuggest(AutoSuggest):
    """Provides live inline ghost suggestions based on SQL semantics, schema, and history."""

    def __init__(self, database: Any) -> None:
        self.database = database
        self._history_suggest = AutoSuggestFromHistory()

    def get_suggestion(self, buffer: Buffer, document: Document) -> Suggestion | None:
        text = document.text_before_cursor
        stripped = text.strip()
        upper = stripped.upper()

        tables = list(self.database.tables.keys()) if self.database and self.database.tables else []
        sample_table = tables[0] if tables else "records"
        cols = self.database.tables.get(sample_table, []) if sample_table in getattr(self.database, "tables", {}) else []
        sample_col = cols[0] if cols else "id"

        # SQL keyword ghost completions
        if upper == "SELECT":
            return Suggestion(f" * FROM `{sample_table}`;")
        if upper == "SELECT *":
            return Suggestion(f" FROM `{sample_table}`;")
        if upper == "CREATE TABLE":
            return Suggestion(" `students` (\n    `id` INT AUTO_INCREMENT PRIMARY KEY,\n    `name` VARCHAR(100) NOT NULL\n);")
        if upper == "CREATE DATABASE":
            return Suggestion(" IF NOT EXISTS `my_database` CHARACTER SET utf8mb4;")
        if upper == "INSERT INTO":
            return Suggestion(f" `{sample_table}` () VALUES ();")
        if upper == "ALTER TABLE":
            return Suggestion(f" `{sample_table}` ADD COLUMN `new_column` VARCHAR(100);")
        if upper == "DROP TABLE":
            return Suggestion(f" IF EXISTS `{sample_table}`;")
        if upper == "DELETE FROM":
            return Suggestion(f" `{sample_table}` WHERE `{sample_col}` = 1;")
        if upper == "UPDATE":
            return Suggestion(f" `{sample_table}` SET `{sample_col}` = 1 WHERE `{sample_col}` = 0;")
        if upper == "FROM":
            return Suggestion(f" `{sample_table}`")
        if upper.endswith("WHERE"):
            return Suggestion(f" `{sample_col}` = ")
        if upper.endswith("ORDER BY"):
            return Suggestion(f" `{sample_col}` DESC LIMIT 10;")
        if upper.endswith("GROUP BY"):
            return Suggestion(f" `{sample_col}`")
        if upper.endswith("INNER JOIN") or upper.endswith("LEFT JOIN"):
            t2 = tables[1] if len(tables) > 1 else "other_table"
            return Suggestion(f" `{t2}` ON `{sample_table}`.`id` = `{t2}`.`{sample_table}_id`")

        # Command ghost completions
        if upper == ":USE":
            dbs = getattr(self.database, "database_names", [])
            target = dbs[0] if dbs else "my_db"
            return Suggestion(f" {target}")
        if upper == ":DESCRIBE" or upper == ":SAMPLE" or upper == ":COUNT":
            return Suggestion(f" {sample_table}")
        if upper == ":AUTOPILOT" or upper == ":AUTO":
            return Suggestion(" create table students with id, name, and email")
        if upper == ":LEARN" or upper == ":TUTOR":
            return Suggestion(" create-table")

        # Fallback to history matching
        return self._history_suggest.get_suggestion(buffer, document)
