"""Context-aware MySQL completion backed by the selected database schema."""

from __future__ import annotations

import re

from prompt_toolkit.completion import Completer, Completion

KEYWORDS = "SELECT FROM WHERE JOIN LEFT RIGHT INNER OUTER ON AS AND OR NOT NULL IS IN LIKE BETWEEN " \
    "GROUP BY ORDER HAVING LIMIT OFFSET INSERT INTO VALUES UPDATE SET DELETE CREATE DATABASE TABLE " \
    "ALTER DROP DISTINCT COUNT SUM AVG MIN MAX CASE WHEN THEN ELSE END DESC ASC SHOW USE " \
    "UNION ALL PRIMARY KEY FOREIGN REFERENCES INDEX DEFAULT AUTO_INCREMENT IF EXISTS".split()
FUNCTIONS = "COUNT SUM AVG MIN MAX COALESCE IFNULL NULLIF CONCAT CONCAT_WS LOWER UPPER TRIM " \
    "LENGTH CHAR_LENGTH ROUND FLOOR CEIL ABS NOW CURDATE DATE YEAR MONTH DAY CAST CONVERT " \
    "GROUP_CONCAT JSON_EXTRACT".split()
TABLE_WORDS = {
    "WHERE", "JOIN", "ON", "SET", "ORDER", "GROUP", "LIMIT", "HAVING", "LEFT", "RIGHT",
    "INNER", "OUTER", "CROSS", "FULL", "UNION", "VALUES", "USING", "FOR", "WINDOW",
}
COLUMN_CLAUSE = re.compile(r"\b(SELECT|WHERE|ON|SET|BY|HAVING|AND|OR)\b", re.IGNORECASE)
CLAUSE_KEYWORDS = {
    "SELECT": "DISTINCT AS FROM CASE WHEN THEN ELSE END",
    "WHERE": "AND OR NOT NULL IS IN LIKE BETWEEN",
    "ON": "AND OR NOT NULL IS IN LIKE BETWEEN",
    "SET": "DEFAULT NULL",
    "BY": "ASC DESC",
    "HAVING": "AND OR NOT NULL IS IN LIKE BETWEEN",
    "AND": "NOT NULL IS IN LIKE BETWEEN",
    "OR": "NOT NULL IS IN LIKE BETWEEN",
}


class SQLCompleter(Completer):
    def __init__(self, database, plugins):
        self.database = database
        self.plugins = plugins

    @staticmethod
    def _statement(text: str) -> str:
        # Keep context local to the current statement in a multi-query buffer.
        return re.split(r";(?=(?:[^'\"]|'[^']*'|\"[^\"]*\")*$)", text)[-1]

    def _tables_in_scope(self, text: str) -> dict[str, str]:
        schema = self.database.tables
        by_lower = {name.lower(): name for name in schema}
        aliases: dict[str, str] = {}
        pattern = r"\b(?:FROM|JOIN|UPDATE|INTO)\s+`?([\w$]+)`?(?:\s+(?:AS\s+)?([\w$]+))?"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            typed_table, alias = match.groups()
            table = by_lower.get(typed_table.lower())
            if not table:
                continue
            aliases[table.lower()] = table
            if alias and alias.upper() not in TABLE_WORDS:
                aliases[alias.lower()] = table
        return aliases

    def get_completions(self, document, complete_event):
        text = self._statement(document.text_before_cursor)
        raw_word = document.get_word_before_cursor(WORD=True)
        word = raw_word.strip("`")
        aliases = self._tables_in_scope(text)

        # A trailing table clause expects table names, not every SQL keyword.
        table_match = re.search(r"\b(?:FROM|JOIN|UPDATE|INTO)\s+([\w$`]*)$", text, re.IGNORECASE)
        if table_match:
            items = list(self.database.tables)
            start_position = -len(raw_word)
        else:
            # In `alias.column`, complete only the part after the dot.
            dot_match = re.search(r"([\w$`]+)\.([\w$`]*)$", text)
            if dot_match:
                qualifier = dot_match.group(1).strip("`").lower()
                suffix = dot_match.group(2).strip("`")
                table = aliases.get(qualifier)
                columns = self.database.tables.get(table, []) if table else []
                word = suffix
                start_position = -len(suffix)
                items = columns
            else:
                start_position = -len(raw_word)
                items = []
                latest_clause = None
                for match in COLUMN_CLAUSE.finditer(text):
                    latest_clause = match.group(1).upper()

                # Offer columns from tables already named in this query. If no
                # table has appeared yet, use this database's schema as a guide.
                scoped_tables = list(dict.fromkeys(aliases.values()))
                if scoped_tables:
                    for table in scoped_tables:
                        items.extend(self.database.tables.get(table, []))
                    # Also offer valid aliases and table-qualified columns in
                    # joins, where unqualified names can be ambiguous.
                    if len(scoped_tables) > 1:
                        items.extend(aliases.keys())
                        for alias, table in aliases.items():
                            items.extend(f"{alias}.{column}" for column in self.database.tables.get(table, []))
                elif latest_clause in {"SELECT", "WHERE", "ON", "SET", "BY", "HAVING", "AND", "OR"}:
                    for columns in self.database.tables.values():
                        items.extend(columns)

                items.extend(CLAUSE_KEYWORDS.get(latest_clause, KEYWORDS))
                items.extend(FUNCTIONS)
                if not scoped_tables and latest_clause not in CLAUSE_KEYWORDS:
                    items.extend(self.database.tables.keys())
                items.extend(self.plugins.completions(text))

        seen = set()
        for item in items:
            if item and item.lower().startswith(word.lower()) and item.lower() not in seen:
                seen.add(item.lower())
                yield Completion(item, start_position=start_position)
