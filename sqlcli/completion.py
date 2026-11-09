"""Context-aware MySQL completion backed by the selected database schema and SQL reference."""

from __future__ import annotations

import re
from difflib import get_close_matches

from prompt_toolkit.completion import Completer, Completion

from .knowledge import list_topics

# Keyword category metadata mapping
METADATA: dict[str, str] = {
    # Clauses
    "SELECT": "Clause: Retrieve rows from tables",
    "FROM": "Clause: Specify source table(s)",
    "WHERE": "Clause: Filter rows by condition",
    "JOIN": "Clause: Combine records from related tables",
    "INNER JOIN": "Clause: Rows matching both tables",
    "LEFT JOIN": "Clause: All left rows + matched right",
    "RIGHT JOIN": "Clause: All right rows + matched left",
    "FULL JOIN": "Clause: Union of left and right joins",
    "CROSS JOIN": "Clause: Cartesian product of all rows",
    "ON": "Clause: Join condition link",
    "AS": "Clause: Rename column or table alias",
    "AND": "Operator: Both conditions must be TRUE",
    "OR": "Operator: Either condition must be TRUE",
    "NOT": "Operator: Invert condition truth value",
    "IN": "Operator: Match any value in list/subquery",
    "BETWEEN": "Operator: Within inclusive range",
    "LIKE": "Operator: Pattern match (% and _)",
    "IS NULL": "Condition: Value is missing/undefined",
    "IS NOT NULL": "Condition: Value is present/defined",
    "GROUP BY": "Clause: Aggregate summary rows by group",
    "HAVING": "Clause: Filter groups after aggregation",
    "ORDER BY": "Clause: Sort result set",
    "ASC": "Order: Ascending sort (A-Z, 0-9)",
    "DESC": "Order: Descending sort (Z-A, 9-0)",
    "LIMIT": "Clause: Cap maximum rows returned",
    "OFFSET": "Clause: Skip initial N rows",
    "DISTINCT": "Clause: Eliminate duplicate rows",
    "UNION": "Clause: Combine queries without duplicates",
    "UNION ALL": "Clause: Combine queries keeping duplicates",
    "INSERT INTO": "Clause: Insert new table rows",
    "VALUES": "Clause: Specify row values to insert",
    "UPDATE": "Clause: Modify existing row values",
    "SET": "Clause: Column value assignment",
    "DELETE FROM": "Clause: Remove matching rows",
    "DELETE": "Clause: Remove matching rows",
    "CASE": "Expression: Conditional IF-THEN-ELSE logic",
    "WHEN": "Case: When condition is true",
    "THEN": "Case: Result when matched",
    "ELSE": "Case: Fallback result",
    "END": "Case: Close CASE statement",
    "EXISTS": "Subquery: TRUE if subquery has rows",
    "SHOW": "Utility: Inspect databases or tables",
    "USE": "Utility: Switch active database schema",
    # DDL
    "CREATE TABLE": "DDL: Define new table schema",
    "CREATE DATABASE": "DDL: Create new database",
    "ALTER TABLE": "DDL: Modify table structure",
    "DROP TABLE": "DDL: Delete table and all rows",
    "DROP DATABASE": "DDL: Delete entire database permanently",
    "TRUNCATE": "DDL: Empty all table rows quickly",
    "ADD COLUMN": "DDL: Add a new column to table",
    "DROP COLUMN": "DDL: Remove column from table",
    "MODIFY COLUMN": "DDL: Change column type/constraints",
    "RENAME TO": "DDL: Rename table to new name",
    # Data types
    "INT": "Type: 4-byte integer (-2.1B to +2.1B)",
    "INTEGER": "Type: Standard integer (synonym for INT)",
    "BIGINT": "Type: 8-byte integer for large IDs",
    "TINYINT": "Type: 1-byte integer (0-255 or boolean)",
    "SMALLINT": "Type: 2-byte integer (-32k to +32k)",
    "MEDIUMINT": "Type: 3-byte integer (-8M to +8M)",
    "VARCHAR(255)": "Type: Variable text up to 255 chars",
    "VARCHAR(100)": "Type: Variable text up to 100 chars",
    "VARCHAR(50)": "Type: Short variable text up to 50 chars",
    "VARCHAR": "Type: Dynamic length character string",
    "CHAR": "Type: Fixed length character string",
    "TEXT": "Type: Long text field up to 64 KB",
    "MEDIUMTEXT": "Type: Medium text field up to 16 MB",
    "LONGTEXT": "Type: Giant text field up to 4 GB",
    "DECIMAL(10, 2)": "Type: Exact money/currency precision",
    "DECIMAL": "Type: Fixed-point exact numeric",
    "FLOAT": "Type: 4-byte floating point number",
    "DOUBLE": "Type: 8-byte double precision float",
    "BOOLEAN": "Type: True/False boolean flag",
    "BOOL": "Type: True/False boolean flag",
    "DATE": "Type: Date 'YYYY-MM-DD'",
    "DATETIME": "Type: Date & time 'YYYY-MM-DD HH:MM:SS'",
    "TIMESTAMP": "Type: Auto-updating timestamp",
    "TIME": "Type: Time 'HH:MM:SS'",
    "YEAR": "Type: 4-digit year 'YYYY'",
    "JSON": "Type: Structured JSON document",
    "BLOB": "Type: Binary large object",
    "ENUM": "Type: Pick one from allowed list",
    # Constraints
    "PRIMARY KEY": "Constraint: Unique row identifier",
    "AUTO_INCREMENT": "Constraint: Sequential auto-increment ID",
    "NOT NULL": "Constraint: Disallow empty/NULL value",
    "NULL": "Constraint: Value is optional (nullable)",
    "UNIQUE": "Constraint: All values must be distinct",
    "CHECK": "Constraint: Validate custom boolean rule",
    "DEFAULT": "Constraint: Default fallback value",
    "FOREIGN KEY": "Constraint: Link to parent table primary key",
    "REFERENCES": "Constraint: Target table and column reference",
    "CASCADE": "Option: Propagate deletion/update to children",
    "RESTRICT": "Option: Block parent deletion if child exists",
    # Functions
    "COUNT(*)": "Aggregate: Total number of rows",
    "COUNT()": "Aggregate: Count non-null column values",
    "SUM()": "Aggregate: Total sum of numeric column",
    "AVG()": "Aggregate: Arithmetic mean of numeric column",
    "MIN()": "Aggregate: Smallest value in column",
    "MAX()": "Aggregate: Largest value in column",
    "GROUP_CONCAT()": "Aggregate: Concatenate grouped string values",
    "CONCAT()": "String: Concatenate strings together",
    "CONCAT_WS()": "String: Concatenate with separator",
    "LOWER()": "String: Convert text to lowercase",
    "UPPER()": "String: Convert text to uppercase",
    "TRIM()": "String: Strip leading & trailing spaces",
    "SUBSTRING()": "String: Extract substring from text",
    "REPLACE()": "String: Replace occurrences of text",
    "LENGTH()": "String: Length of string in bytes",
    "CHAR_LENGTH()": "String: Number of characters in string",
    "ROUND()": "Math: Round number to N decimals",
    "FLOOR()": "Math: Round down to nearest integer",
    "CEIL()": "Math: Round up to nearest integer",
    "ABS()": "Math: Absolute positive value",
    "MOD()": "Math: Remainder of division (modulo)",
    "RAND()": "Math: Random float between 0 and 1",
    "NOW()": "Date: Current date and time timestamp",
    "CURDATE()": "Date: Current date ('YYYY-MM-DD')",
    "CURTIME()": "Date: Current time ('HH:MM:SS')",
    "DATEDIFF()": "Date: Difference in days between two dates",
    "DATE_ADD()": "Date: Add interval to date",
    "DATE_SUB()": "Date: Subtract interval from date",
    "DATE_FORMAT()": "Date: Format date as custom string",
    "IFNULL()": "Flow: Fallback if first value is NULL",
    "COALESCE()": "Flow: Return first non-null expression",
    "IF()": "Flow: Return value based on condition",
    # Commands
    "autopilot": "Command: Natural language query assistant",
    "auto": "Command: Natural language query assistant (alias)",
    "learn": "Command: Browse W3Schools tutorials & examples",
    "tutor": "Command: Interactive SQL learning guide",
    "paste": "Command: Paste SQL from OS clipboard",
    "copy": "Command: Copy last query or custom text to clipboard",
    "save": "Command: Save named query, .sql file, or results",
    "saved": "Command: List all saved query snippets",
    "run": "Command: Run a saved query statement",
    "tables": "Command: List all tables in active database",
    "describe": "Command: Show table columns, types, and keys",
    "columns": "Command: Show table column definitions",
    "sample": "Command: Preview up to 100 rows from table",
    "count": "Command: Count total rows in table",
    "databases": "Command: List all accessible databases",
    "use": "Command: Select active database schema",
    "history": "Command: Review past command history",
    "find": "Command: Search tables and columns by name",
    "export": "Command: Export SELECT query to a CSV file",
    "refresh": "Command: Reload database and schema suggestions",
    "ai": "Command: Toggle or reset local Ollama assistance",
    "ollama": "Command: Start, pull, or check local Ollama status",
    "ask": "Command: Suggest SQL using local Ollama model",
    "chat": "Command: Chat with local assistant",
    "help": "Command: Show command reference guide",
    "quit": "Command: Exit SQLCLI workbench",
}

KEYWORDS = (
    "SELECT FROM WHERE JOIN LEFT RIGHT INNER OUTER FULL CROSS ON AS AND OR NOT NULL IS IN LIKE BETWEEN "
    "GROUP BY ORDER HAVING LIMIT OFFSET INSERT INTO VALUES UPDATE SET DELETE CREATE DATABASE TABLE "
    "ALTER DROP DISTINCT COUNT SUM AVG MIN MAX CASE WHEN THEN ELSE END DESC ASC SHOW USE "
    "UNION ALL PRIMARY KEY FOREIGN REFERENCES INDEX DEFAULT AUTO_INCREMENT IF EXISTS INTERVAL "
    "DATE TIME DATETIME TIMESTAMP ADD COLUMN MODIFY CHANGE RENAME TO UNIQUE CHECK CONSTRAINT "
    "TRUNCATE CASCADE RESTRICT TRIGGER PROCEDURE FUNCTION VIEW ENGINE DEFAULT CHARSET COLLATE "
    "EXISTS ANY ALL IN OUT INOUT DELIMITER START TRANSACTION COMMIT ROLLBACK"
).split()

DATA_TYPES = (
    "INT INTEGER BIGINT SMALLINT TINYINT MEDIUMINT DECIMAL DECIMAL(10,2) NUMERIC FLOAT DOUBLE "
    "VARCHAR(255) VARCHAR(100) VARCHAR(50) VARCHAR CHAR TEXT MEDIUMTEXT LONGTEXT TINYTEXT "
    "BOOLEAN BOOL DATE DATETIME TIMESTAMP TIME YEAR BLOB JSON ENUM"
).split()

TABLE_CONSTRAINTS = (
    "NOT NULL AUTO_INCREMENT PRIMARY KEY UNIQUE CHECK DEFAULT FOREIGN KEY REFERENCES "
    "ON DELETE CASCADE ON DELETE SET NULL ON DELETE RESTRICT ON UPDATE CASCADE"
).split()

FUNCTIONS = (
    "COUNT(*) COUNT() SUM() AVG() MIN() MAX() COALESCE() IFNULL() NULLIF() CONCAT() CONCAT_WS() "
    "LOWER() UPPER() TRIM() LENGTH() CHAR_LENGTH() ROUND() FLOOR() CEIL() ABS() NOW() CURDATE() "
    "CURTIME() DATE_ADD() DATE_SUB() DATEDIFF() DATE_FORMAT() GROUP_CONCAT() JSON_EXTRACT() "
    "SUBSTRING() REPLACE() REVERSE() RAND() MOD() IF()"
).split()

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
    "CREATE": "DATABASE TABLE INDEX VIEW PROCEDURE FUNCTION",
    "ALTER": "TABLE DATABASE ADD DROP MODIFY CHANGE RENAME TO",
    "DROP": "DATABASE TABLE INDEX VIEW PROCEDURE",
    "LIMIT": "OFFSET",
}


class SQLCompleter(Completer):
    COMMANDS = (
        "connect", "use", "databases", "tables", "describe", "columns", "sample", "count",
        "export", "refresh", "history", "find", "save", "saved", "run",
        "ai", "ollama", "ask", "chat", "plugins", "help", "quit", "exit",
        "autopilot", "auto", "learn", "tutor", "paste", "copy",
    )
    COMMAND_ARGUMENTS = {
        "describe": (),
        "columns": (),
        "sample": (),
        "count": (),
        "find": (),
        "run": (),
        "ai": ("on", "off", "reset"),
        "ollama": ("start", "status", "pull"),
        "autopilot": (),
        "auto": (),
        "paste": ("run",),
        "copy": ("last", "sql", "output"),
        "save": ("file", "output"),
    }

    def __init__(self, database, plugins):
        self.database = database
        self.plugins = plugins

    @staticmethod
    def _statement(text: str) -> str:
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

    def _matching(self, items: list[str], word: str, start_position: int):
        """Yield unique case-insensitive prefix matches with rich display metadata."""
        seen = set()
        matches = [item for item in items if item and item.lower().startswith(word.lower())]
        fuzzy = False
        if not matches and len(word) >= 3:
            matches = get_close_matches(word, list(dict.fromkeys(i for i in items if i)), n=6, cutoff=0.65)
            fuzzy = bool(matches)

        for item in matches:
            norm = item.lower()
            if norm not in seen:
                seen.add(norm)
                meta = ""
                # Lookup rich metadata
                upper_item = item.upper()
                if upper_item in METADATA:
                    meta = METADATA[upper_item]
                elif item in getattr(self.database, "tables", {}):
                    cols = self.database.tables[item]
                    summary_cols = ", ".join(cols[:2]) + (", ..." if len(cols) > 2 else "")
                    meta = f"Table: {len(cols)} cols ({summary_cols})"
                elif any(item in cols for cols in getattr(self.database, "tables", {}).values()):
                    for t_name, t_cols in getattr(self.database, "tables", {}).items():
                        if item in t_cols:
                            meta = f"Column in `{t_name}`"
                            break
                elif norm in METADATA:
                    meta = METADATA[norm]
                elif fuzzy:
                    meta = "Similar name"

                yield Completion(
                    item,
                    start_position=start_position,
                    display_meta=meta,
                )

    def _command_completions(self, text: str):
        """Complete SQLCLI commands and their arguments with rich metadata."""
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
        if command == "find":
            items.extend(self.database.tables)
            items.extend(column for columns in self.database.tables.values() for column in columns)
        if command == "run":
            try:
                from .queries import load_queries
                items.extend(load_queries())
            except RuntimeError:
                pass
        if command in {"learn", "tutor"}:
            items.extend(list_topics())
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

        # Smart foreign key link suggestion on `JOIN ... ON`
        join_on_match = re.search(r"\bJOIN\s+`?([\w$]+)`?\s+ON\s+([\w$.`]*)$", text, re.IGNORECASE)
        if join_on_match:
            joined_table = join_on_match.group(1).lower()
            typed_so_far = join_on_match.group(2)
            links = []
            for scope_alias, scope_table in aliases.items():
                if scope_table.lower() != joined_table:
                    # Suggest common id links e.g. orders.user_id = users.id
                    links.append(f"`{scope_alias}`.`id` = `{joined_table}`.`{scope_alias}_id`")
                    links.append(f"`{joined_table}`.`{scope_alias}_id` = `{scope_alias}`.`id`")
                    links.append(f"`{scope_alias}`.`{joined_table}_id` = `{joined_table}`.`id`")
            if links:
                yield from self._matching(links, typed_so_far, -len(typed_so_far))
                return

        # CREATE TABLE (...) column definition context: offer data types, constraints, and snippets
        create_table_match = re.search(r"\bCREATE\s+TABLE\s+`?([\w$]+)`?\s*\([^)]*$", text, re.IGNORECASE)
        if create_table_match:
            create_items = list(DATA_TYPES) + list(TABLE_CONSTRAINTS) + [
                "INT AUTO_INCREMENT PRIMARY KEY",
                "VARCHAR(255) NOT NULL",
                "VARCHAR(100) NOT NULL UNIQUE",
                "DECIMAL(10, 2) NOT NULL DEFAULT 0.00",
                "BOOLEAN NOT NULL DEFAULT TRUE",
                "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "TEXT NULL",
            ]
            yield from self._matching(create_items, word, -len(raw_word))
            return

        # ALTER TABLE <table> context: offer alter actions
        alter_table_match = re.search(r"\bALTER\s+TABLE\s+`?([\w$]+)`?\s+([\w$]*)$", text, re.IGNORECASE)
        if alter_table_match:
            alter_items = [
                "ADD COLUMN", "DROP COLUMN", "MODIFY COLUMN", "CHANGE COLUMN", "RENAME TO",
                "ADD PRIMARY KEY", "ADD CONSTRAINT", "ADD FOREIGN KEY", "ADD INDEX",
            ]
            yield from self._matching(alter_items, word, -len(raw_word))
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

                # Offer columns from tables already named in this query.
                scoped_tables = list(dict.fromkeys(aliases.values()))
                if scoped_tables:
                    if column_context:
                        for table in scoped_tables:
                            items.extend(self.database.tables.get(table, []))
                        if len(scoped_tables) > 1:
                            items.extend(aliases.keys())
                            for alias, table in aliases.items():
                                items.extend(f"{alias}.{column}" for column in self.database.tables.get(table, []))
                elif column_context:
                    for columns in self.database.tables.values():
                        items.extend(columns)

                if not insert_column_list:
                    clause_keywords = CLAUSE_KEYWORDS.get(latest_clause)
                    items.extend(clause_keywords.split() if clause_keywords else KEYWORDS)
                if latest_clause not in NON_EXPRESSION_CONTEXTS:
                    items.extend(FUNCTIONS)
                if not scoped_tables and latest_clause not in CLAUSE_KEYWORDS:
                    items.extend(self.database.tables.keys())

        items.extend(self.plugins.completions(before_cursor))
        yield from self._matching(items, word, start_position)
