"""Context-aware MySQL completion backed by the selected database schema."""

from __future__ import annotations

import re

from prompt_toolkit.completion import Completer, Completion

KEYWORDS = "SELECT FROM WHERE JOIN LEFT RIGHT INNER OUTER ON AS AND OR NOT NULL IS IN LIKE BETWEEN " \
    "GROUP BY ORDER HAVING LIMIT OFFSET INSERT INTO VALUES UPDATE SET DELETE CREATE DATABASE TABLE " \
    "ALTER DROP DISTINCT COUNT SUM AVG MIN MAX CASE WHEN THEN ELSE END DESC ASC SHOW USE " \
    "UNION ALL PRIMARY KEY FOREIGN REFERENCES INDEX DEFAULT AUTO_INCREMENT IF EXISTS INTERVAL " \
    "DATE TIME DATETIME TIMESTAMP".split()
FUNCTIONS = "COUNT SUM AVG MIN MAX COALESCE IFNULL NULLIF CONCAT CONCAT_WS LOWER UPPER TRIM " \
    "LENGTH CHAR_LENGTH ROUND FLOOR CEIL ABS NOW CURDATE DATE YEAR MONTH DAY CAST CONVERT " \
    "GROUP_CONCAT JSON_EXTRACT ADDDATE ADDTIME CONVERT_TZ CURTIME CURRENT_DATE CURRENT_TIME " \
    "CURRENT_TIMESTAMP DATE_ADD DATE_FORMAT DATE_SUB DATEDIFF DAYNAME DAYOFMONTH DAYOFWEEK " \
    "DAYOFYEAR EXTRACT FROM_DAYS FROM_UNIXTIME HOUR LAST_DAY LOCALTIME LOCALTIMESTAMP " \
    "MAKEDATE MAKETIME MICROSECOND MINUTE MONTHNAME PERIOD_ADD PERIOD_DIFF QUARTER " \
    "SEC_TO_TIME SECOND STR_TO_DATE SUBDATE SUBTIME TIME TIME_FORMAT TIMEDIFF TIMESTAMP " \
    "TIMESTAMPADD TIMESTAMPDIFF TO_DAYS TO_SECONDS UNIX_TIMESTAMP UTC_DATE UTC_TIME " \
    "UTC_TIMESTAMP WEEK WEEKDAY WEEKOFYEAR YEARWEEK".split()
INTERVAL_UNITS = "MICROSECOND SECOND MINUTE HOUR DAY WEEK MONTH QUARTER YEAR".split()
COLUMN_CONTEXTS = {"SELECT", "WHERE", "ON", "SET", "GROUP BY", "ORDER BY", "HAVING", "AND", "OR"}
NON_EXPRESSION_CONTEXTS = {
    "FROM", "JOIN", "INSERT", "INTO", "UPDATE", "DELETE", "SHOW", "CREATE", "ALTER", "DROP", "LIMIT",
}
TABLE_WORDS = {
    "WHERE", "JOIN", "ON", "SET", "ORDER", "GROUP", "LIMIT", "HAVING", "LEFT", "RIGHT",
    "INNER", "OUTER", "CROSS", "FULL", "UNION", "VALUES", "USING", "FOR", "WINDOW",
}
SQL_CONTEXT = re.compile(
    r"\b(SELECT|FROM|WHERE|JOIN|ON|SET|GROUP\s+BY|ORDER\s+BY|HAVING|AND|OR|"
    r"INSERT|INTO|UPDATE|DELETE|SHOW|CREATE|ALTER|DROP|LIMIT)\b",
    re.IGNORECASE,
)
CLAUSE_KEYWORDS = {
    "SELECT": "DISTINCT AS FROM CASE WHEN THEN ELSE END *",
    "FROM": "JOIN LEFT RIGHT INNER CROSS WHERE GROUP BY ORDER BY LIMIT",
    "JOIN": "ON USING LEFT RIGHT INNER CROSS",
    "WHERE": "AND OR NOT NULL IS IN LIKE BETWEEN",
    "ON": "AND OR NOT NULL IS IN LIKE BETWEEN",
    "SET": "DEFAULT NULL",
    "GROUP BY": "ASC DESC WITH ROLLUP",
    "ORDER BY": "ASC DESC",
    "HAVING": "AND OR NOT NULL IS IN LIKE BETWEEN",
    "AND": "NOT NULL IS IN LIKE BETWEEN",
    "OR": "NOT NULL IS IN LIKE BETWEEN",
    "INSERT": "INTO",
    "INTO": "VALUES SELECT",
    "UPDATE": "SET",
    "DELETE": "FROM",
    "SHOW": "DATABASES TABLES COLUMNS STATUS VARIABLES",
    "CREATE": "DATABASE TABLE INDEX VIEW",
    "ALTER": "TABLE DATABASE",
    "DROP": "DATABASE TABLE INDEX VIEW",
    "LIMIT": "OFFSET",
}


class SQLCompleter(Completer):
    COMMANDS = (
        "connect", "use", "databases", "tables", "describe", "columns", "sample", "count",
        "export", "refresh", "ai", "ollama", "ask", "plugins", "help", "quit", "exit",
    )
    COMMAND_ARGUMENTS = {
        "describe": (),
        "columns": (),
        "sample": (),
        "count": (),
        "ai": ("on", "off", "reset"),
        "ollama": ("start", "status", "pull"),
    }

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

    @staticmethod
    def _matching(items: list[str], word: str, start_position: int):
        """Yield unique case-insensitive prefix matches in their original form."""
        seen = set()
        for item in items:
            if item and item.lower().startswith(word.lower()) and item.lower() not in seen:
                seen.add(item.lower())
                yield Completion(item, start_position=start_position)

    def _command_completions(self, text: str):
        """Complete SQLCLI commands and their simple local arguments."""
        command_match = re.search(r"(?:^|\s):([\w-]*)$", text)
        if command_match:
            word = command_match.group(1)
            names = list(self.COMMANDS) + list(self.plugins.commands)
            names = list(dict.fromkeys(names))
            return self._matching(names, word, -len(word))

        argument_match = re.search(r"(?:^|\s):([\w-]+)\s+([^\s]*)$", text)
        if not argument_match:
            return None

        command, word = argument_match.groups()
        command = command.lower()
        items = list(self.COMMAND_ARGUMENTS.get(command, ()))
        if command in {"use", "connect"}:
            items.extend(self.database.database_names)
        if command in {"describe", "columns", "sample", "count"}:
            items.extend(self.database.tables)
        items.extend(self.plugins.completions(text))
        return self._matching(items, word, -len(word))

    def get_completions(self, document, complete_event):
        before_cursor = document.text_before_cursor
        if before_cursor.lstrip().startswith(":"):
            command_items = self._command_completions(before_cursor)
            if command_items is not None:
                yield from command_items
                return

        text = self._statement(before_cursor)
        raw_word = document.get_word_before_cursor(WORD=True)
        word = raw_word.strip("`")
        aliases = self._tables_in_scope(text)

        # DATE_ADD/DATE_SUB/TIMESTAMPADD use a unit keyword after INTERVAL.
        if re.search(r"\bINTERVAL\s+[\w+-]*$", text, re.IGNORECASE):
            yield from self._matching(INTERVAL_UNITS, word, -len(raw_word))
            return

        # A trailing table clause expects table names, not every SQL keyword.
        table_match = re.search(r"\b(?:FROM|JOIN|UPDATE|INTO|DESCRIBE)\s+([\w$`]*)$", text, re.IGNORECASE)
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
                context_matches = list(SQL_CONTEXT.finditer(text))
                latest_clause = context_matches[-1].group(1).upper() if context_matches else None
                if latest_clause:
                    latest_clause = " ".join(latest_clause.split())
                insert_column_list = re.search(
                    r"\bINSERT\s+INTO\s+`?([\w$]+)`?\s*\([^)]*$", text, re.IGNORECASE
                )
                column_context = latest_clause in COLUMN_CONTEXTS or bool(insert_column_list)

                # Offer columns from tables already named in this query. If no
                # table has appeared yet, use this database's schema as a guide.
                scoped_tables = list(dict.fromkeys(aliases.values()))
                if scoped_tables:
                    if column_context:
                        for table in scoped_tables:
                            items.extend(self.database.tables.get(table, []))
                        # Also offer valid aliases and table-qualified columns
                        # in joins, where unqualified names can be ambiguous.
                        if len(scoped_tables) > 1:
                            items.extend(aliases.keys())
                            for alias, table in aliases.items():
                                items.extend(f"{alias}.{column}" for column in self.database.tables.get(table, []))
                elif column_context:
                    for columns in self.database.tables.values():
                        items.extend(columns)

                if not insert_column_list:
                    clause_keywords = CLAUSE_KEYWORDS.get(latest_clause)
                    # CLAUSE_KEYWORDS stores phrases as strings; split them so
                    # prompt_toolkit completes whole words instead of one
                    # suggestion per character (for example F, R, O, M).
                    items.extend(clause_keywords.split() if clause_keywords else KEYWORDS)
                if latest_clause not in NON_EXPRESSION_CONTEXTS:
                    items.extend(FUNCTIONS)
                if not scoped_tables and latest_clause not in CLAUSE_KEYWORDS:
                    items.extend(self.database.tables.keys())

        # Plugin callbacks receive the complete text before the cursor and are
        # consulted in every context, including table names and alias columns.
        items.extend(self.plugins.completions(before_cursor))
        yield from self._matching(items, word, start_position)
