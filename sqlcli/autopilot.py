"""Advanced Autopilot engine: translates natural language goals to production SQL with interactive review."""

from __future__ import annotations

import re
from typing import Any

from tabulate import tabulate

from .ai import suggest_sql
from .knowledge import lookup_topic
from .sql_safety import inspect_sql


def _clean_ident(name: str) -> str:
    """Sanitize identifier names for backticked SQL usage."""
    return re.sub(r"[^\w$]", "_", name.strip().strip("`"))


def _infer_column_def(col_name: str, explicit_type: str = "") -> str:
    """Infer optimal MySQL column type, nullability, and constraints from name."""
    col_name = _clean_ident(col_name)
    if explicit_type:
        return f"`{col_name}` {explicit_type.upper()}"

    lower = col_name.lower()
    if lower == "email":
        return f"`{col_name}` VARCHAR(150) NOT NULL UNIQUE"
    if any(k in lower for k in ["name", "title", "subject", "label", "heading"]):
        return f"`{col_name}` VARCHAR(100) NOT NULL"
    if any(k in lower for k in ["pass", "hash", "secret", "token"]):
        return f"`{col_name}` VARCHAR(255) NOT NULL"
    if any(k in lower for k in ["phone", "mobile", "tel", "zip", "postal"]):
        return f"`{col_name}` VARCHAR(25) NULL"
    if any(k in lower for k in ["price", "amount", "salary", "cost", "total", "balance", "fee"]):
        return f"`{col_name}` DECIMAL(10, 2) NOT NULL DEFAULT 0.00"
    if any(k in lower for k in ["age", "count", "qty", "quantity", "views", "stock", "score", "points"]):
        return f"`{col_name}` INT NOT NULL DEFAULT 0"
    if any(k in lower for k in ["is_", "has_", "active", "enabled", "verified", "admin", "deleted"]):
        default_val = "FALSE" if "admin" in lower or "deleted" in lower else "TRUE"
        return f"`{col_name}` BOOLEAN NOT NULL DEFAULT {default_val}"
    if any(k in lower for k in ["bio", "desc", "content", "comment", "body", "text", "notes"]):
        return f"`{col_name}` TEXT NULL"
    if any(k in lower for k in ["birth", "dob", "start_date", "end_date"]):
        return f"`{col_name}` DATE NULL"
    if lower.endswith("_id") or lower.endswith("id"):
        return f"`{col_name}` INT NOT NULL"
    if any(k in lower for k in ["created", "updated", "time"]):
        return f"`{col_name}` TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    return f"`{col_name}` VARCHAR(255) NULL"


def rule_based_sql_generator(goal: str, database: Any = None, engine: str = "mysql") -> tuple[str, str, str] | None:
    """Generate high-accuracy SQL from natural-language goals without external AI.

    Returns: (sql, category, explanation) or None if no rule matches.
    """
    text = goal.strip().rstrip(";. ")
    lower = text.lower()
    eng = (engine or "mysql").lower()
    tables = getattr(database, "tables", {}) if database else (database if isinstance(database, dict) else {})

    # 1. CREATE DATABASE
    match = re.match(r"(?:create|make|new)\s+(?:a\s+)?database\s+(?:called\s+|named\s+)?([`\w$]+)", text, re.IGNORECASE)
    if match:
        db_name = _clean_ident(match.group(1))
        sql = f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        return sql, "DDL (Schema)", f"Creates a new UTF-8 database schema named '{db_name}'."

    # 2. CREATE TABLE with smart column parsing & foreign keys
    match = re.match(
        r"(?:create|make|new)\s+(?:a\s+)?table\s+(?:called\s+|named\s+|for\s+)?([`\w$]+)(?:\s+(?:with|having|containing)\s+(.+))?",
        text,
        re.IGNORECASE,
    )
    if match and match.group(1).lower() not in {"database", "databases"}:
        table_name = _clean_ident(match.group(1))
        columns_raw = match.group(2) or ""

        if eng == "sqlite":
            columns_sql: list[str] = ["    `id` INTEGER PRIMARY KEY AUTOINCREMENT"]
        else:
            columns_sql = ["    `id` INT AUTO_INCREMENT PRIMARY KEY"]
        fk_clauses: list[str] = []

        if columns_raw:
            # Check for foreign key references in natural language (e.g. "foreign key to users", "linked to customers")
            fk_matches = re.finditer(r"(?:foreign\s+key\s+(?:to\s+|in\s+)|linked\s+to\s+|references\s+)([`\w$]+)", columns_raw, re.IGNORECASE)
            for fkm in fk_matches:
                target_parent = _clean_ident(fkm.group(1))
                fk_col = f"{target_parent.rstrip('s')}_id"
                columns_sql.append(f"    `{fk_col}` INT NOT NULL")
                fk_clauses.append(f"    FOREIGN KEY (`{fk_col}`) REFERENCES `{target_parent}`(`id`) ON DELETE CASCADE")

            # Remove foreign key phrases from raw column definitions before column split
            cleaned_cols = re.sub(r"(?:foreign\s+key\s+(?:to\s+|in\s+)|linked\s+to\s+|references\s+)[`\w$]+", "", columns_raw, flags=re.IGNORECASE)

            # Split columns by comma or "and"
            raw_parts = [p.strip() for p in re.split(r",|\band\b", cleaned_cols) if p.strip()]
            for part in raw_parts:
                words = part.split()
                if not words:
                    continue
                # Recognize two-word column names e.g. "first name", "last name", "user id", "phone number"
                if len(words) >= 2 and words[1].lower() in {
                    "name", "id", "date", "hash", "number", "at", "admin", "active", "code", "price", "amount"
                }:
                    col_name = f"{words[0]}_{words[1]}"
                    explicit_type = " ".join(words[2:])
                else:
                    col_name = words[0]
                    explicit_type = " ".join(words[1:])

                if col_name.lower() in {"id", "primary", "foreign", "key"}:
                    continue
                columns_sql.append("    " + _infer_column_def(col_name, explicit_type))

        columns_sql.append("    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        all_lines = columns_sql + fk_clauses
        col_block = ",\n".join(all_lines)
        if eng == "sqlite":
            sql = f"CREATE TABLE IF NOT EXISTS `{table_name}` (\n{col_block}\n);"
            return sql, "DDL (Schema)", f"Defines SQLite table '{table_name}' with primary key and typed columns."
        sql = f"CREATE TABLE IF NOT EXISTS `{table_name}` (\n{col_block}\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
        return sql, "DDL (Schema)", f"Defines table '{table_name}' with primary key, typed columns, and InnoDB storage engine."

    # 3. TOP N / RANKING QUERIES
    top_match = re.match(
        r"(?:(?:show|list|get|find|select)\s+)?(?:the\s+)?(?:top|first|latest|newest)\s+(\d+)\s+(.+)",
        text,
        re.IGNORECASE,
    )
    if top_match:
        limit = top_match.group(1)
        rest = top_match.group(2).strip()
        in_match = re.search(r"\b(?:in|from|of)\s+([`\w$]+)", rest, re.IGNORECASE)
        tbl_candidate = _clean_ident(in_match.group(1)) if in_match else "records"
        col_match = re.search(r"\b(?:by|ordered\s+by)\s+([`\w$]+)", rest, re.IGNORECASE)
        if col_match:
            sort_col = _clean_ident(col_match.group(1))
        else:
            cleaned_rest = re.sub(r"\b(?:in|from|of)\s+[`\w$]+", "", rest, flags=re.IGNORECASE)
            col_words = [
                w for w in cleaned_rest.split()
                if w.lower() not in {"highest", "lowest", "most", "expensive", "cheapest", "best", "worst", "records", "rows", "data", "the"}
            ]
            sort_col = _clean_ident(col_words[0]) if col_words else "id"

        desc = "ASC" if any(w in lower for w in ["lowest", "cheapest", "oldest", "worst"]) else "DESC"
        sql = f"SELECT * FROM `{tbl_candidate}` ORDER BY `{sort_col}` {desc} LIMIT {limit};"
        return sql, "Query (Ranking)", f"Retrieves top {limit} records from '{tbl_candidate}' ordered by '{sort_col}' {desc}."

    # 4. DUPLICATE FINDER
    dup_match = re.match(r"(?:find|show|list|get)\s+duplicates?\s+(?:of\s+|for\s+|in\s+)?([`\w$]+)?(?:\s+(?:in|from)\s+([`\w$]+))?", text, re.IGNORECASE)
    if dup_match and ("duplicate" in lower or "duplicates" in lower):
        col = dup_match.group(1) or "email"
        tbl = dup_match.group(2) or "users"
        if tbl not in tables and col in tables:
            col, tbl = "id", col
        sql = f"SELECT `{col}`, COUNT(*) AS `duplicate_count` FROM `{tbl}` GROUP BY `{col}` HAVING `duplicate_count` > 1 ORDER BY `duplicate_count` DESC;"
        return sql, "Query (Duplicates)", f"Finds duplicate values of column '{col}' in table '{tbl}' using GROUP BY and HAVING."

    # 5. AGGREGATION & SUMMARY (COUNT / SUM / AVG BY CATEGORY)
    agg_match = re.match(
        r"(?:count|sum|average|avg|calculate)\s+(?:total\s+|all\s+)?([`\w$]+)?\s+(?:in|from|of)\s+([`\w$]+)(?:\s+(?:grouped\s+by|by|per)\s+([`\w$]+))?",
        text,
        re.IGNORECASE,
    )
    if agg_match and ("count" in lower or "sum" in lower or "average" in lower or "avg" in lower):
        target_col = agg_match.group(1) or "*"
        target_table = agg_match.group(2)
        group_col = agg_match.group(3)

        if "sum" in lower:
            func = f"SUM(`{target_col}`)"
            alias = f"total_{target_col}"
        elif "avg" in lower or "average" in lower:
            func = f"ROUND(AVG(`{target_col}`), 2)"
            alias = f"avg_{target_col}"
        else:
            func = "COUNT(*)"
            alias = "total_count"

        if group_col:
            sql = f"SELECT `{group_col}`, {func} AS `{alias}` FROM `{target_table}` GROUP BY `{group_col}` ORDER BY `{alias}` DESC;"
            return sql, "Query (Aggregation)", f"Computes {func} for each unique '{group_col}' in '{target_table}'."
        sql = f"SELECT {func} AS `{alias}` FROM `{target_table}`;"
        return sql, "Query (Aggregation)", f"Calculates overall aggregate {func} across '{target_table}'."

    # 6. JOINS
    join_match = re.match(
        r"(?:join|combine|merge)\s+([`\w$]+)\s+(?:and|with)\s+([`\w$]+)(?:\s+(?:on|by)\s+(.+))?",
        text,
        re.IGNORECASE,
    )
    if join_match:
        t1, t2 = _clean_ident(join_match.group(1)), _clean_ident(join_match.group(2))
        on_raw = join_match.group(3)
        if on_raw:
            on_clause = on_raw.strip()
        else:
            # Infer join key: e.g. orders.user_id = users.id
            t2_singular = t2.rstrip("s")
            t1_singular = t1.rstrip("s")
            on_clause = f"`{t1}`.`{t2_singular}_id` = `{t2}`.`id`"
        sql = f"SELECT * FROM `{t1}` INNER JOIN `{t2}` ON {on_clause} LIMIT 50;"
        return sql, "Query (Join)", f"Combines matching records from tables '{t1}' and '{t2}'."

    # 7. DATE-FILTERED SELECTS ("TODAY", "THIS WEEK", "THIS MONTH")
    if "today" in lower and any(v in lower for v in ["orders", "users", "records", "logs", "sales"]):
        tbl_match = re.search(r"\b([a-zA-Z_]\w*)\b", text)
        target = tbl_match.group(1) if tbl_match else "orders"
        if eng == "sqlite":
            sql = f"SELECT * FROM `{target}` WHERE DATE(`created_at`) = DATE('now') ORDER BY `created_at` DESC LIMIT 50;"
        else:
            sql = f"SELECT * FROM `{target}` WHERE DATE(`created_at`) = CURDATE() ORDER BY `created_at` DESC LIMIT 50;"
        return sql, "Query (Date Filter)", f"Retrieves all rows in '{target}' created today."

    if any(p in lower for p in ["last 7 days", "past week", "this week"]):
        tbl = re.search(r"(?:in|from|of)\s+([`\w$]+)", text, re.IGNORECASE)
        target = tbl.group(1) if tbl else "records"
        if eng == "sqlite":
            sql = f"SELECT * FROM `{target}` WHERE `created_at` >= DATETIME('now', '-7 days') ORDER BY `created_at` DESC LIMIT 50;"
        else:
            sql = f"SELECT * FROM `{target}` WHERE `created_at` >= DATE_SUB(NOW(), INTERVAL 7 DAY) ORDER BY `created_at` DESC LIMIT 50;"
        return sql, "Query (Date Filter)", f"Filters '{target}' for rows in the past 7 days."

    # 8. ADD COLUMN
    match = re.match(
        r"add\s+column\s+([`\w$]+)\s+([a-zA-Z0-9_() ]+?)\s+(?:to\s+|in\s+)([`\w$]+)",
        text,
        re.IGNORECASE,
    )
    if match:
        col_name = _clean_ident(match.group(1))
        col_type = match.group(2).strip().upper()
        tbl_name = _clean_ident(match.group(3))
        sql = f"ALTER TABLE `{tbl_name}` ADD COLUMN `{col_name}` {col_type};"
        return sql, "DDL (Schema Change)", f"Alters '{tbl_name}' to append column '{col_name}' ({col_type})."

    # 9. DROP TABLE
    match = re.match(r"(?:drop|delete|remove)\s+table\s+([`\w$]+)", text, re.IGNORECASE)
    if match and "from" not in lower:
        tbl_name = _clean_ident(match.group(1))
        return f"DROP TABLE IF EXISTS `{tbl_name}`;", "DDL (Destructive)", f"Permanently removes table '{tbl_name}' and all stored records."

    # 10. GENERAL SELECT / LIST
    match = re.match(
        r"(?:show|list|get|find|select|view)\s+(?:all\s+)?(?:records\s+|rows\s+|data\s+)?(?:from\s+|in\s+)?([`\w$]+)(?:\s+where\s+(.+))?",
        text,
        re.IGNORECASE,
    )
    if match and match.group(1).lower() not in {"databases", "tables"}:
        table_name = _clean_ident(match.group(1))
        where_clause = match.group(2)
        if where_clause:
            sql = f"SELECT * FROM `{table_name}` WHERE {where_clause} LIMIT 50;"
            return sql, "Query (Filtered)", f"Queries records from '{table_name}' matching conditions."
        return f"SELECT * FROM `{table_name}` LIMIT 50;", "Query (Read-Only)", f"Selects up to 50 rows from '{table_name}'."

    return None


def generate_autopilot_plan(
    goal: str,
    database: Any,
    settings: Any,
    engine: str = "mysql",
) -> tuple[str, str, str]:
    """Return (sql, category, explanation) via rule engine, local AI, or knowledge base."""
    # 1. Advanced rule engine
    matched = rule_based_sql_generator(goal, database, engine=engine)
    if matched:
        return matched

    # 2. Local Ollama AI
    if getattr(settings, "ai_enabled", False):
        try:
            sql = suggest_sql(goal, database, settings.ollama_url, settings.ollama_model)
            if not sql.startswith("CLARIFY:"):
                return sql, "AI Synthesis (Ollama)", f"Synthesized from your schema and prompt: '{goal}'."
        except Exception:
            pass

    # 3. Knowledge base fallback
    topic = lookup_topic(goal)
    if topic:
        return topic.example.splitlines()[0], "SQL Reference Example", f"Matched W3Schools topic '{topic.name}'."

    clean = re.sub(r"[^\w\s]", "", goal).strip()
    return f"SELECT '{clean}' AS query_note;", "Generic Template", "Could not parse intent; fallback query generated."


def run_autopilot(
    goal: str,
    database: Any,
    settings: Any,
    session: Any,
) -> str | None:
    """Interactively review and execute autopilot SQL.

    Returns: SQL string to populate prompt buffer if user chooses [E]dit, else None.
    """
    if not goal.strip():
        print("Usage: :autopilot <what you want to accomplish>")
        print("Examples:")
        print("  :autopilot create table users with first name, last name, email, password, and age")
        print("  :autopilot top 10 highest paid employees")
        print("  :autopilot find duplicate emails in users")
        print("  :autopilot join orders and customers")
        print("  :autopilot orders from today")
        return None

    sql, category, explanation = generate_autopilot_plan(goal, database, settings)
    safety = inspect_sql(sql)

    border = "═" * 70
    print(f"\n\033[1;36m╔{border}╗\033[0m")
    print(f"\033[1;36m║  ✈  SQLCLI AUTOPILOT PLAN\033[0m{' ' * 44}\033[1;36m║\033[0m")
    print(f"\033[1;36m╠{border}╣\033[0m")
    print(f"║  \033[1mGoal:\033[0m {goal[:60]:<62} ║")
    print(f"║  \033[1mType:\033[0m {category[:60]:<62} ║")
    print(f"║  \033[1mInfo:\033[0m {explanation[:60]:<62} ║")
    print(f"\033[1;36m╠{border}╣\033[0m")
    print("║  \033[1;32mGenerated SQL:\033[0m                                                     ║")
    for line in sql.splitlines():
        print(f"║    \033[1;32m{line:<64}\033[0m ║")
    print(f"\033[1;36m╚{border}╝\033[0m\n")

    if safety.missing_where:
        print("\033[1;31mBlocked for safety: Statement needs a WHERE clause.\033[0m\n")
        return None

    verb = (safety.verb or "").upper()
    if verb in {"CREATE", "ALTER", "INSERT", "UPDATE", "DELETE", "SELECT"} and not getattr(settings, "database", None):
        if "DATABASE" not in sql.upper():
            print("\033[1;33mNotice: No database selected.\033[0m")
            try:
                db_name = session.prompt("Enter database name to use (or Enter to cancel): ").strip()
            except KeyboardInterrupt:
                db_name = ""
            if not db_name:
                print("Autopilot cancelled.")
                return None
            try:
                database.connect(db_name)
                print(f"Connected to database '{db_name}'.")
            except Exception as exc:
                print(f"Connection failed: {exc}")
                return None

    try:
        choice = session.prompt("\033[1m[Y]es run now  ·  [E]dit in prompt  ·  [C]ancel: \033[0m").strip().lower()
    except KeyboardInterrupt:
        choice = "c"

    if choice in {"", "y", "yes"}:
        try:
            headers, rows, count = database.execute(sql)
            if headers:
                print(tabulate(rows or [], headers=headers, tablefmt="rounded_grid", showindex=False))
                print(f"\n{len(rows or [])} row(s) returned.")
            else:
                print(f"\nQuery OK, {count} row(s) affected.")
                if verb in {"CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME"}:
                    database.refresh_schema()
                    try:
                        database.refresh_databases()
                    except Exception:
                        pass
                    print("Schema refreshed.")
        except Exception as exc:
            print(f"Execution failed: {exc}")
        return None
    elif choice in {"e", "edit"}:
        print("Loaded statement into prompt buffer. Press Enter to run or edit.")
        return sql
    else:
        print("Cancelled.")
        return None
