"""Visual SQL diagnostics and beginner-friendly error analysis for CLI and Terminal Studio."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SQLDiagnostic:
    error_type: str
    error_code: int | None
    line_number: int
    column_offset: int
    faulty_snippet: str
    message: str
    explanation: str
    suggested_fix: str | None
    plain_summary: str = ""
    why_failed: str = ""
    rule_tip: str = ""
    corrected_sql: str | None = None


COMMON_TYPOS: dict[str, str] = {
    "FORM": "FROM",
    "FRO": "FROM",
    "FRM": "FROM",
    "WHER": "WHERE",
    "WHERR": "WHERE",
    "WERE": "WHERE",
    "SELCT": "SELECT",
    "SELEC": "SELECT",
    "SLCT": "SELECT",
    "SLECT": "SELECT",
    "SELECTT": "SELECT",
    "INSRT": "INSERT",
    "INSER": "INSERT",
    "INSTERT": "INSERT",
    "UPDAT": "UPDATE",
    "UPDT": "UPDATE",
    "UODATE": "UPDATE",
    "DELET": "DELETE",
    "DELTE": "DELETE",
    "DELEET": "DELETE",
    "CRATE": "CREATE",
    "CREAT": "CREATE",
    "TABEL": "TABLE",
    "TABLES": "TABLE",
    "GRUP": "GROUP",
    "GROP": "GROUP",
    "HAVNG": "HAVING",
    "HVING": "HAVING",
    "ORDAR": "ORDER",
    "ODER": "ORDER",
    "VALUS": "VALUES",
    "VALU": "VALUES",
    "VALUSE": "VALUES",
    "DISTINT": "DISTINCT",
    "DISTINCTT": "DISTINCT",
    "JOINN": "JOIN",
    "JON": "JOIN",
    "PRIMRY": "PRIMARY",
    "PRMARY": "PRIMARY",
    "FORIEGN": "FOREIGN",
    "FORIGN": "FOREIGN",
    "LIMT": "LIMIT",
    "LIMITT": "LIMIT",
}

SQL_KEYWORDS: list[str] = [
    "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES", "UPDATE", "SET",
    "DELETE", "CREATE", "TABLE", "DROP", "ALTER", "GROUP", "BY", "HAVING",
    "ORDER", "ASC", "DESC", "LIMIT", "JOIN", "INNER", "LEFT", "RIGHT", "ON",
    "AND", "OR", "NOT", "IN", "BETWEEN", "LIKE", "IS", "NULL", "PRIMARY",
    "KEY", "FOREIGN", "REFERENCES", "DEFAULT", "CHECK", "UNIQUE", "DISTINCT",
]


def _extract_schema(database: Any) -> dict[str, list[str]]:
    """Normalize database or schema object into dict[table_name, list[column_names]]."""
    if not database:
        return {}
    if isinstance(database, dict):
        return database
    if hasattr(database, "get_schema"):
        try:
            return database.get_schema()
        except Exception:
            pass
    if hasattr(database, "tables") and isinstance(database.tables, dict):
        return database.tables
    return {}


def analyze_error(
    sql: str,
    error: Exception | str,
    database: Any = None,
    engine: str = "sqlite",
) -> SQLDiagnostic:
    """Analyze SQL and error to triangulate root cause, friendly explanation, and auto-fix."""
    err_str = str(error)
    errno = getattr(error, "errno", None)
    sql_clean = sql.strip()
    sql_lines = sql_clean.splitlines() if sql_clean else [""]
    line_count = len(sql_lines)
    schema = _extract_schema(database)

    # 1. MySQL Offline / Connection Refused
    if any(k in err_str for k in ("Can't connect to MySQL server", "Connection refused", "10061", "2003 (HY000)")):
        return SQLDiagnostic(
            error_type="DATABASE_OFFLINE",
            error_code=2003,
            line_number=1,
            column_offset=1,
            faulty_snippet="localhost:3306",
            message=err_str,
            explanation="The MySQL server daemon is not responding on port 3306.",
            suggested_fix="Press [F2] in Terminal Studio to switch to zero-setup SQLite, or start MySQL in XAMPP.",
            plain_summary="MySQL is offline. No database server is running on port 3306.",
            why_failed="Your computer tried to contact MySQL, but nothing answered because XAMPP MySQL is not running.",
            rule_tip="Tip: Press [F2] anytime to switch to SQLite — SQLite needs zero setup and works instantly!",
            corrected_sql=None,
        )

    # 2. No Database Selected (MySQL 1046)
    if errno == 1046 or "No database selected" in err_str:
        return SQLDiagnostic(
            error_type="DATABASE_MISSING",
            error_code=1046,
            line_number=1,
            column_offset=1,
            faulty_snippet=sql_lines[0] if sql_lines else "",
            message=err_str,
            explanation="No database is currently selected. MySQL does not know where to store or look for tables.",
            suggested_fix="Run ':use <database>' or execute 'CREATE DATABASE mydb; USE mydb;' first.",
            plain_summary="No database selected.",
            why_failed="MySQL manages multiple independent databases. It needs to know which database to open.",
            rule_tip="Rule: Always select a database with 'USE database_name;' before running queries.",
            corrected_sql=f"CREATE DATABASE IF NOT EXISTS my_workspace;\nUSE my_workspace;\n{sql_clean}",
        )

    # 3. Table Not Found (MySQL 1146 / SQLite no such table)
    table_match = re.search(
        r"(?:Table '[\w$]+\.([\w$]+)' doesn't exist|no such table:\s*([`\w$]+))",
        err_str,
        re.IGNORECASE,
    )
    if table_match:
        missing_table = table_match.group(1) or table_match.group(2)
        tables = list(schema.keys())
        closest = difflib.get_close_matches(missing_table, tables, n=1, cutoff=0.5)

        line_num = 1
        for i, line in enumerate(sql_lines, 1):
            if re.search(r"\b" + re.escape(missing_table) + r"\b", line, re.IGNORECASE):
                line_num = i
                break

        if closest:
            corrected = re.sub(
                r"\b" + re.escape(missing_table) + r"\b",
                closest[0],
                sql_clean,
                flags=re.IGNORECASE,
            )
            return SQLDiagnostic(
                error_type="TABLE_NOT_FOUND",
                error_code=errno or 1146,
                line_number=line_num,
                column_offset=1,
                faulty_snippet=missing_table,
                message=err_str,
                explanation=f"Table '{missing_table}' does not exist in the database.",
                suggested_fix=f"Change table name '{missing_table}' to '{closest[0]}'.",
                plain_summary=f"Table '{missing_table}' not found. Did you mean '{closest[0]}'?",
                why_failed=f"The database cannot find '{missing_table}'. Found a similarly named table: '{closest[0]}'.",
                rule_tip=f"Rule: Table names must match exactly. Available tables: {', '.join(tables)}.",
                corrected_sql=corrected,
            )

        if not tables:
            return SQLDiagnostic(
                error_type="TABLE_NOT_FOUND",
                error_code=errno or 1146,
                line_number=line_num,
                column_offset=1,
                faulty_snippet=missing_table,
                message=err_str,
                explanation=f"Table '{missing_table}' does not exist. The active database has zero tables.",
                suggested_fix="Press [F3] to seed sample 'students' and 'courses' tables, or run CREATE TABLE.",
                plain_summary=f"Table '{missing_table}' does not exist. Your database is completely empty.",
                why_failed="You haven't created any tables yet, so there is no data to query.",
                rule_tip="Tip: Press [F3] in Terminal Studio to seed sample tables instantly!",
                corrected_sql="CREATE TABLE students (\n    id INTEGER PRIMARY KEY,\n    name TEXT,\n    major TEXT,\n    gpa REAL\n);\n",
            )

        return SQLDiagnostic(
            error_type="TABLE_NOT_FOUND",
            error_code=errno or 1146,
            line_number=line_num,
            column_offset=1,
            faulty_snippet=missing_table,
            message=err_str,
            explanation=f"The database cannot find table '{missing_table}'.",
            suggested_fix=f"Check table spelling. Available tables: {', '.join(tables)}.",
            plain_summary=f"Table '{missing_table}' does not exist.",
            why_failed=f"The database has no table named '{missing_table}'. Current tables: {', '.join(tables)}.",
            rule_tip="Rule: Check the Tables & Schema panel on the left to see all existing tables.",
            corrected_sql=None,
        )

    # 4. Missing Quotes around Text Literal (treated as Unknown Column)
    col_match = re.search(
        r"(?:Unknown column '([\w$]+)'|no such column:\s*([`\w$]+))",
        err_str,
        re.IGNORECASE,
    )
    if col_match:
        missing_col = col_match.group(1) or col_match.group(2)
        line_num = 1
        for i, line in enumerate(sql_lines, 1):
            if re.search(r"\b" + re.escape(missing_col) + r"\b", line):
                line_num = i
                break

        # Check if missing_col appears on the right of an operator (e.g. WHERE name = John)
        literal_pattern = re.compile(
            r"(=|!=|<>|LIKE)\s*([`'\"]?)" + re.escape(missing_col) + r"([`'\"]?)",
            re.IGNORECASE,
        )
        if literal_pattern.search(sql_clean):
            corrected = literal_pattern.sub(r"\1 '" + missing_col + "'", sql_clean)
            return SQLDiagnostic(
                error_type="MISSING_QUOTES",
                error_code=errno or 1054,
                line_number=line_num,
                column_offset=1,
                faulty_snippet=missing_col,
                message=err_str,
                explanation=f"SQL treated '{missing_col}' as a column name because it lacked single quotes.",
                suggested_fix=f"Enclose text in single quotes: '{missing_col}'.",
                plain_summary=f"Missing quotes: '{missing_col}' was treated as a column name.",
                why_failed=f"Without quotes, SQL assumes '{missing_col}' is a column in your table, not a text value.",
                rule_tip=f"Rule: Text values must always be enclosed in single quotes like '{missing_col}'. Numbers do not need quotes.",
                corrected_sql=corrected,
            )

        # Check if column is a typo of an existing column in schema
        all_cols: list[str] = []
        for cols in schema.values():
            all_cols.extend(cols)
        closest_col = difflib.get_close_matches(missing_col, all_cols, n=1, cutoff=0.5)
        if closest_col:
            corrected = re.sub(
                r"\b" + re.escape(missing_col) + r"\b",
                closest_col[0],
                sql_clean,
            )
            return SQLDiagnostic(
                error_type="COLUMN_NOT_FOUND",
                error_code=errno or 1054,
                line_number=line_num,
                column_offset=1,
                faulty_snippet=missing_col,
                message=err_str,
                explanation=f"Column '{missing_col}' does not exist.",
                suggested_fix=f"Change column '{missing_col}' to '{closest_col[0]}'.",
                plain_summary=f"Column '{missing_col}' not found. Did you mean '{closest_col[0]}'?",
                why_failed=f"The table does not contain a column named '{missing_col}'. Closest column found: '{closest_col[0]}'.",
                rule_tip="Rule: Column names must match table definitions. Check the Schema explorer panel.",
                corrected_sql=corrected,
            )

        return SQLDiagnostic(
            error_type="COLUMN_NOT_FOUND",
            error_code=errno or 1054,
            line_number=line_num,
            column_offset=1,
            faulty_snippet=missing_col,
            message=err_str,
            explanation=f"Column '{missing_col}' does not exist in the referenced table(s).",
            suggested_fix="Check column spelling. Look at the Tables & Schema panel on the left.",
            plain_summary=f"Column '{missing_col}' does not exist.",
            why_failed=f"SQL cannot find a column called '{missing_col}' in the table you are querying.",
            rule_tip="Rule: Check available columns in the left Schema panel or run ':describe <table>'.",
            corrected_sql=None,
        )

    # 5. Table Already Exists (CREATE TABLE when table already present)
    if "already exists" in err_str.lower():
        tbl_match = re.search(r"table\s+['\"]?([\w$]+)['\"]?\s+already exists", err_str, re.IGNORECASE)
        tbl_name = tbl_match.group(1) if tbl_match else "table"
        corrected = re.sub(
            r"\bCREATE\s+TABLE\s+",
            "CREATE TABLE IF NOT EXISTS ",
            sql_clean,
            flags=re.IGNORECASE,
        )
        return SQLDiagnostic(
            error_type="TABLE_ALREADY_EXISTS",
            error_code=errno or 1050,
            line_number=1,
            column_offset=1,
            faulty_snippet=tbl_name,
            message=err_str,
            explanation=f"Table '{tbl_name}' already exists in this database.",
            suggested_fix="Use 'CREATE TABLE IF NOT EXISTS ...' or DROP the existing table first.",
            plain_summary=f"Table '{tbl_name}' already exists in the database.",
            why_failed="You cannot create a table with a name that is already taken.",
            rule_tip="Rule: Add 'IF NOT EXISTS' to your CREATE TABLE statement to avoid errors when re-running scripts.",
            corrected_sql=corrected,
        )

    # 6. Duplicate Primary Key / Unique Constraint Failed
    if any(k in err_str.lower() for k in ("unique constraint failed", "duplicate entry")):
        return SQLDiagnostic(
            error_type="DUPLICATE_KEY",
            error_code=errno or 1062,
            line_number=1,
            column_offset=1,
            faulty_snippet="PRIMARY KEY",
            message=err_str,
            explanation="A row with this primary key or unique value already exists.",
            suggested_fix="Use a different ID number or use UPDATE to modify the existing record.",
            plain_summary="Duplicate key error: A record with this ID already exists.",
            why_failed="Primary keys must be 100% unique for every single row. You tried to insert an ID that was already taken.",
            rule_tip="Rule: Primary keys uniquely identify rows. Consider AUTOINCREMENT so the database handles IDs for you.",
            corrected_sql=None,
        )

    # 7. NOT NULL Constraint Failed
    if any(k in err_str.lower() for k in ("not null constraint failed", "doesn't have a default value")):
        col_req = re.search(r"(?:not null constraint failed:\s*[\w$.]+\.([\w$]+)|Field '([\w$]+)' doesn't have a default value)", err_str, re.IGNORECASE)
        req_name = col_req.group(1) or col_req.group(2) if col_req else "column"
        return SQLDiagnostic(
            error_type="NOT_NULL_VIOLATION",
            error_code=errno or 1364,
            line_number=1,
            column_offset=1,
            faulty_snippet=req_name,
            message=err_str,
            explanation=f"Column '{req_name}' was configured as NOT NULL and cannot be left blank.",
            suggested_fix=f"Include column '{req_name}' and provide a value in your INSERT statement.",
            plain_summary=f"Required column '{req_name}' cannot be empty.",
            why_failed=f"The table schema requires a value for '{req_name}'. You omitted it or passed NULL.",
            rule_tip=f"Rule: Columns defined with NOT NULL require a value on every INSERT.",
            corrected_sql=None,
        )

    # 8. Misuse of Aggregate Function in WHERE
    if any(k in err_str.lower() for k in ("misuse of aggregate", "invalid use of group function")):
        return SQLDiagnostic(
            error_type="AGGREGATE_IN_WHERE",
            error_code=errno or 1111,
            line_number=1,
            column_offset=1,
            faulty_snippet="WHERE ... aggregate()",
            message=err_str,
            explanation="Aggregate functions like COUNT(), SUM(), AVG(), MIN(), MAX() cannot be used in a WHERE clause.",
            suggested_fix="Use HAVING instead of WHERE to filter calculated values (e.g., HAVING COUNT(*) > 5).",
            plain_summary="Cannot use aggregate functions (COUNT, SUM, AVG) inside a WHERE clause.",
            why_failed="WHERE filters individual rows before grouping. To filter summary calculations, you must use HAVING.",
            rule_tip="Rule: Use WHERE for raw row filters, and HAVING for grouped calculations.",
            corrected_sql=None,
        )

    # 9. Trailing Comma (before ')' or before FROM)
    comma_paren_match = re.search(r",(\s*\))", sql_clean)
    comma_from_match = re.search(r",(\s+FROM\b)", sql_clean, re.IGNORECASE)
    if (comma_paren_match or comma_from_match) and "syntax error" in err_str.lower():
        if comma_paren_match:
            corrected = sql_clean[:comma_paren_match.start()] + comma_paren_match.group(1) + sql_clean[comma_paren_match.end():]
        else:
            corrected = sql_clean[:comma_from_match.start()] + comma_from_match.group(1) + sql_clean[comma_from_match.end():]
        return SQLDiagnostic(
            error_type="TRAILING_COMMA",
            error_code=errno or 1064,
            line_number=1,
            column_offset=1,
            faulty_snippet=",",
            message=err_str,
            explanation="An extra comma was placed before ')' or 'FROM'.",
            suggested_fix="Remove the extra trailing comma. Press [F6] to auto-fix.",
            plain_summary="Extra trailing comma found before ')' or 'FROM'.",
            why_failed="In SQL, commas separate list items. Putting a comma at the end makes the database look for another column that does not exist.",
            rule_tip="Rule: Never leave a trailing comma after the last column in SELECT or CREATE TABLE.",
            corrected_sql=corrected,
        )

    # 10. Unbalanced Parentheses
    open_p = sql_clean.count("(")
    close_p = sql_clean.count(")")
    if open_p > close_p and ("syntax error" in err_str.lower() or "incomplete input" in err_str.lower()):
        missing_count = open_p - close_p
        fixed = sql_clean.rstrip().rstrip(";") + (")" * missing_count) + ";"
        return SQLDiagnostic(
            error_type="UNBALANCED_PARENTHESES",
            error_code=errno or 1064,
            line_number=line_count,
            column_offset=1,
            faulty_snippet="(",
            message=err_str,
            explanation=f"Missing closing parenthesis. Found {open_p} '(' but only {close_p} ')'.",
            suggested_fix="Add ')' to close all opened parentheses. Press [F6] to auto-fix.",
            plain_summary=f"Missing closing parenthesis ')': You opened {open_p} '(' but closed {close_p}.",
            why_failed="Every opening parenthesis '(' in SQL must have a matching closing parenthesis ')'.",
            rule_tip="Rule: Match every '(' with a ')' before the final semicolon.",
            corrected_sql=fixed,
        )

    # 11. Wrong Clause Order (WHERE before FROM)
    where_match = re.search(r"\bWHERE\b", sql_clean, re.IGNORECASE)
    from_match = re.search(r"\bFROM\b", sql_clean, re.IGNORECASE)
    if where_match and from_match and where_match.start() < from_match.start() and "syntax error" in err_str.lower():
        return SQLDiagnostic(
            error_type="CLAUSE_ORDER_ERROR",
            error_code=errno or 1064,
            line_number=1,
            column_offset=1,
            faulty_snippet="WHERE ... FROM",
            message=err_str,
            explanation="The WHERE clause was written before the FROM clause.",
            suggested_fix="Move the 'FROM <table>' clause before the 'WHERE <condition>' clause.",
            plain_summary="Wrong clause order: WHERE cannot come before FROM.",
            why_failed="SQL must know which table to inspect (FROM) before it can filter any rows (WHERE).",
            rule_tip="Rule: Order must always be SELECT -> FROM -> WHERE -> GROUP BY -> HAVING -> ORDER BY -> LIMIT.",
            corrected_sql=None,
        )

    # 12. NoSQL Document Syntax Error
    if any(k in err_str for k in ("JSONDecodeError", "Expecting property name enclosed in double quotes", "Unknown NoSQL operation")):
        return SQLDiagnostic(
            error_type="NOSQL_SYNTAX_ERROR",
            error_code=None,
            line_number=1,
            column_offset=1,
            faulty_snippet="{...}",
            message=err_str,
            explanation="Invalid NoSQL document syntax. JSON keys and string values must be in double quotes.",
            suggested_fix='Enclose keys and string values in double quotes, e.g., db.users.insert({"name": "Alice"})',
            plain_summary="NoSQL syntax error: Malformed JSON document.",
            why_failed="NoSQL document commands require strict JSON format with double quotes around all keys and strings.",
            rule_tip="Rule: Use standard JSON syntax: db.<collection>.insert({\"key\": \"value\"}).",
            corrected_sql=None,
        )

    # 13. Keyword Typo or Syntax Error near Token
    near_match = re.search(r"near\s+['\"]?([^'\"\s:]+)['\"]?(?:\s+at line (\d+))?", err_str, re.IGNORECASE)
    near_token = near_match.group(1).strip() if near_match else ""
    first_tok = near_token.split()[0].strip() if near_token else ""
    line_num = int(near_match.group(2)) if near_match and near_match.group(2) else 1

    # Check for direct typo in common typos
    lookup_tok = first_tok.upper()
    correct_kw = COMMON_TYPOS.get(lookup_tok)

    # If not in common typos, check fuzzy match against SQL keywords
    if not correct_kw and first_tok:
        fuzzy = difflib.get_close_matches(first_tok.upper(), SQL_KEYWORDS, n=1, cutoff=0.75)
        if fuzzy:
            correct_kw = fuzzy[0]

    if correct_kw:
        corrected = re.sub(
            r"\b" + re.escape(first_tok) + r"\b",
            correct_kw,
            sql_clean,
            flags=re.IGNORECASE,
        )
        return SQLDiagnostic(
            error_type="SYNTAX_ERROR",
            error_code=errno or 1064,
            line_number=min(line_num, line_count),
            column_offset=1,
            faulty_snippet=first_tok,
            message=err_str,
            explanation=f"Misspelled SQL keyword '{first_tok}'. Did you mean '{correct_kw}'?",
            suggested_fix=f"replace '{first_tok}' with '{correct_kw}'. Press [F6] to auto-fix.",
            plain_summary=f"Typo in keyword: You wrote '{first_tok}' instead of '{correct_kw}'.",
            why_failed=f"SQL commands are strict. It saw '{first_tok}' and didn't understand what you wanted it to do.",
            rule_tip=f"Rule: '{correct_kw}' is the valid SQL command.",
            corrected_sql=corrected,
        )

    # 14. Fallback General Syntax Error
    faulty_sample = first_tok or (sql_lines[0] if sql_lines else "")
    return SQLDiagnostic(
        error_type="SYNTAX_ERROR",
        error_code=errno or 1064,
        line_number=min(line_num, line_count),
        column_offset=1,
        faulty_snippet=faulty_sample,
        message=err_str,
        explanation="The SQL parser encountered an unexpected token or malformed clause structure.",
        suggested_fix="Check spelling, punctuation, quotes, and clause ordering. Press [F7] for W3Schools tutorials.",
        plain_summary=f"SQL syntax error: Database could not understand your query.",
        why_failed=f"Unexpected text near '{faulty_sample}'. Check for missing keywords, mismatched parentheses, or missing commas.",
        rule_tip="Rule: Standard SELECT syntax: SELECT <columns> FROM <table> WHERE <condition>;",
        corrected_sql=None,
    )


def format_cli_error_box(diag: SQLDiagnostic, sql: str) -> str:
    """Render a crystal-clear, beginner-friendly diagnostic card for the terminal."""
    border = "-" * 68
    lines = [
        f"\n\033[1;31m+{border}+\033[0m",
        f"\033[1;31m|  [X]  SQL EXECUTION ERROR ({diag.error_type})\033[0m{' ' * max(0, 39 - len(diag.error_type))}\033[1;31m|\033[0m",
        f"\033[1;31m+{border}+\033[0m",
    ]

    # Show code line with error caret pointer
    sql_lines = sql.strip().splitlines()
    if 1 <= diag.line_number <= len(sql_lines):
        target_line = sql_lines[diag.line_number - 1]
        lines.append(f"|  Line {diag.line_number}: {target_line[:58]:<58}|")
        if diag.faulty_snippet and diag.faulty_snippet in target_line:
            idx = target_line.find(diag.faulty_snippet)
            pointer = " " * (idx + 8) + "^" * max(1, len(diag.faulty_snippet))
            lines.append(f"\033[1;33m|  {pointer[:64]:<64}\033[0m|")

    lines.append(f"\033[1;31m+{border}+\033[0m")
    lines.append(f"|  \033[1mProblem:\033[0m {diag.plain_summary[:58]:<58}|")
    lines.append(f"|  \033[1mWhy:    \033[0m {diag.why_failed[:58]:<58}|")
    lines.append(f"|  \033[1mRule:   \033[0m {diag.rule_tip[:58]:<58}|")
    if diag.suggested_fix:
        lines.append(f"|  \033[1;32mFix:    \033[0m \033[1;32m{diag.suggested_fix[:58]:<58}\033[0m|")
    if diag.corrected_sql:
        clean_patch = diag.corrected_sql.strip().replace("\n", " ")
        lines.append(f"|  \033[1;36mPatch:  \033[0m \033[1;36m{clean_patch[:58]:<58}\033[0m|")
    lines.append(f"\033[1;31m+{border}+\033[0m\n")
    return "\n".join(lines)
