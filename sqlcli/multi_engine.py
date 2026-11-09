"""Multi-engine manager supporting SQL (MySQL), SQLite, and NoSQL document store."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import Settings
from .connection import Database
from .sql_safety import split_sql_statements


@dataclass
class ExecutionRecord:
    id: str
    engine: str
    query: str
    status: str  # "SUCCESS" or "ERROR"
    row_count: int
    elapsed_ms: float
    error_message: str | None
    timestamp: str


class SQLiteEngine:
    """Zero-setup local SQLite database engine."""

    def __init__(self, db_path: str = "workspace.sqlite") -> None:
        self.is_memory = str(db_path) == ":memory:"
        if self.is_memory:
            self.db_path = Path(":memory:")
        else:
            self.db_path = Path(db_path).resolve()
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection: sqlite3.Connection | None = None
        self.connect()

    def connect(self) -> None:
        target = ":memory:" if self.is_memory else str(self.db_path)
        self.connection = sqlite3.connect(target, autocommit=True, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row

    def get_schema(self) -> dict[str, list[str]]:
        if not self.connection:
            return {}
        cursor = self.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]
        schema: dict[str, list[str]] = {}
        for table in tables:
            cursor.execute(f"PRAGMA table_info(`{table}`);")
            schema[table] = [row[1] for row in cursor.fetchall()]
        return schema

    def get_schema_details(self) -> dict[str, list[dict[str, Any]]]:
        if not self.connection:
            return {}
        cursor = self.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]
        schema: dict[str, list[dict[str, Any]]] = {}
        for table in tables:
            cursor.execute(f"PRAGMA table_info(`{table}`);")
            schema[table] = [
                {
                    "name": row[1],
                    "type": (row[2] or "TEXT").upper(),
                    "is_pk": bool(row[5]),
                    "is_auto": bool(row[5] and "INT" in (row[2] or "").upper()),
                }
                for row in cursor.fetchall()
            ]
        return schema

    def execute(self, sql: str) -> tuple[list[str] | None, list[tuple] | None, int]:
        if not self.connection:
            self.connect()
        statements = split_sql_statements(sql)
        if not statements:
            statements = [sql]
        cursor = self.connection.cursor()
        headers: list[str] | None = None
        rows: list[tuple] | None = None
        total_affected = 0
        for stmt in statements:
            # Ignore MySQL-only USE or CREATE DATABASE statements safely in SQLite
            if re.match(r"^\s*(?:USE|CREATE\s+DATABASE)\b", stmt, re.IGNORECASE):
                continue
            cursor.execute(stmt)
            if cursor.description:
                headers = [d[0] for d in cursor.description]
                rows = [tuple(row) for row in cursor.fetchall()]
                total_affected = len(rows)
            else:
                headers = None
                rows = None
                if cursor.rowcount and cursor.rowcount > 0:
                    total_affected += cursor.rowcount
                else:
                    total_affected = cursor.rowcount
        return headers, rows, total_affected

    def close(self) -> None:
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None


class NoSQLEngine:
    """Document store supporting JSON collections with CRUD & MongoDB-like syntax."""

    def __init__(self, db_path: str = "workspace_nosql.db") -> None:
        self.is_memory = str(db_path) == ":memory:"
        if self.is_memory:
            self.db_path = Path(":memory:")
        else:
            self.db_path = Path(db_path).resolve()
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        target = ":memory:" if self.is_memory else str(self.db_path)
        self.conn = sqlite3.connect(target, autocommit=True, check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nosql_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection TEXT NOT NULL,
                data JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nosql_coll ON nosql_documents(collection);")

    def get_collections(self) -> list[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT collection FROM nosql_documents ORDER BY collection;")
        return [row[0] for row in cursor.fetchall()]

    def get_schema(self) -> dict[str, list[str]]:
        collections = self.get_collections()
        schema: dict[str, list[str]] = {}
        cursor = self.conn.cursor()
        for coll in collections:
            cursor.execute("SELECT data FROM nosql_documents WHERE collection = ? LIMIT 5;", (coll,))
            sample_keys = set()
            for row in cursor.fetchall():
                try:
                    doc = json.loads(row[0])
                    if isinstance(doc, dict):
                        sample_keys.update(doc.keys())
                except Exception:
                    pass
            schema[coll] = sorted(sample_keys) if sample_keys else ["_id", "data"]
        return schema

    def insert(self, collection: str, document: dict[str, Any]) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO nosql_documents (collection, data) VALUES (?, ?);",
            (collection, json.dumps(document, default=str)),
        )
        return cursor.lastrowid or 1

    def update_by_id(self, collection: str, doc_id: int | str, updates: dict[str, Any]) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT data FROM nosql_documents WHERE collection = ? AND id = ?;",
            (collection, int(doc_id)),
        )
        row = cursor.fetchone()
        if not row:
            return 0
        try:
            doc = json.loads(row[0])
            if not isinstance(doc, dict):
                doc = {}
        except Exception:
            doc = {}
        for k, v in updates.items():
            if k not in {"_id", "_created_at"}:
                doc[k] = v
        cursor.execute(
            "UPDATE nosql_documents SET data = ? WHERE collection = ? AND id = ?;",
            (json.dumps(doc, default=str), collection, int(doc_id)),
        )
        return cursor.rowcount

    def delete_by_id(self, collection: str, doc_id: int | str) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM nosql_documents WHERE collection = ? AND id = ?;",
            (collection, int(doc_id)),
        )
        return cursor.rowcount

    def find(self, collection: str, query_filter: dict[str, Any] | None = None, limit: int = 50) -> list[dict[str, Any]]:
        cursor = self.conn.cursor()
        if not query_filter:
            cursor.execute(
                "SELECT id, data, created_at FROM nosql_documents WHERE collection = ? ORDER BY id DESC LIMIT ?;",
                (collection, limit),
            )
        else:
            clauses = ["collection = ?"]
            params: list[Any] = [collection]
            for key, val in query_filter.items():
                clauses.append(f"json_extract(data, '$.{key}') = ?")
                params.append(val)
            sql = f"SELECT id, data, created_at FROM nosql_documents WHERE {' AND '.join(clauses)} ORDER BY id DESC LIMIT ?;"
            params.append(limit)
            cursor.execute(sql, params)

        results = []
        for row in cursor.fetchall():
            try:
                doc = json.loads(row[1])
                doc["_id"] = row[0]
                doc["_created_at"] = row[2]
                results.append(doc)
            except Exception:
                results.append({"_id": row[0], "raw": row[1]})
        return results

    def execute_command(self, cmd: str) -> tuple[list[str] | None, list[tuple] | None, int]:
        """Execute MongoDB-style shell commands: db.<collection>.<action>(<args>)."""
        stripped = cmd.strip().rstrip(";")
        lower = stripped.lower()

        if lower in {"show collections", "collections"}:
            colls = self.get_collections()
            return ["Collection"], [(c,) for c in colls], len(colls)

        match = re.match(r"^db\.([\w$]+)\.([a-zA-Z]+)\((.*)\)$", stripped, re.DOTALL)
        if not match:
            # Fallback: Treat as collection view if plain collection name
            coll_name = stripped.strip("`'\"")
            docs = self.find(coll_name)
            if docs:
                headers = list(docs[0].keys())
                rows = [tuple(doc.get(h, "") for h in headers) for doc in docs]
                return headers, rows, len(rows)
            raise RuntimeError(
                "NoSQL Syntax: Use db.<collection>.find(), db.<collection>.insert({data}), "
                "db.<collection>.delete({filter}), or 'show collections';"
            )

        collection, action, args_str = match.groups()
        action = action.lower()

        if action in {"find", "select"}:
            query_filter = json.loads(args_str) if args_str.strip() else None
            docs = self.find(collection, query_filter)
            if not docs:
                return ["Status"], [("No matching documents found.",)], 0
            headers = ["_id"] + [k for k in docs[0].keys() if k not in {"_id", "_created_at"}] + ["_created_at"]
            rows = [tuple(doc.get(h, "") for h in headers) for doc in docs]
            return headers, rows, len(rows)

        if action in {"insert", "insertone", "add"}:
            doc = json.loads(args_str)
            if not isinstance(doc, dict):
                raise RuntimeError("Document to insert must be a JSON object: { ... }")
            new_id = self.insert(collection, doc)
            return ["Status", "_id"], [(f"Inserted document into collection '{collection}'", new_id)], 1

        if action in {"delete", "remove", "deleteone", "deletemany"}:
            query_filter = json.loads(args_str) if args_str.strip() else None
            if not query_filter:
                raise RuntimeError("Delete requires a filter object, e.g. db.users.delete({\"id\": 1})")
            clauses = ["collection = ?"]
            params: list[Any] = [collection]
            for k, v in query_filter.items():
                if k == "_id":
                    clauses.append("id = ?")
                    params.append(int(v))
                else:
                    clauses.append(f"json_extract(data, '$.{k}') = ?")
                    params.append(v)
            cursor = self.conn.cursor()
            cursor.execute(f"DELETE FROM nosql_documents WHERE {' AND '.join(clauses)};", params)
            return ["Status", "Affected"], [("Deleted documents", cursor.rowcount)], cursor.rowcount

        raise RuntimeError(f"Unknown NoSQL operation: '{action}'. Supported: find(), insert(), delete().")

    def close(self) -> None:
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None


class MultiEngineManager:
    """Coordinates execution across SQL (MySQL), SQLite, and NoSQL."""

    def __init__(
        self,
        settings: Settings,
        mysql_db: Database,
        sqlite_path: str = "workspace.sqlite",
        nosql_path: str = "workspace_nosql.db",
    ) -> None:
        self.settings = settings
        self.mysql = mysql_db
        self.sqlite = SQLiteEngine(sqlite_path)
        self.nosql = NoSQLEngine(nosql_path)
        self.active_engine: str = "mysql"  # "mysql", "sqlite", "nosql"
        self._history_file = Path.home() / ".sqlcli_workbench_history.json"

    def load_history(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self._history_file.exists():
            return []
        try:
            records = json.loads(self._history_file.read_text(encoding="utf-8"))
            return records[-limit:]
        except Exception:
            return []

    def log_execution(self, record: ExecutionRecord) -> None:
        history = self.load_history(100)
        history.append(asdict(record))
        try:
            self._history_file.write_text(json.dumps(history[-100:], indent=2), encoding="utf-8")
        except Exception:
            pass

    def check_mysql_status(self) -> bool:
        """Check if MySQL server is actively reachable in real-time."""
        import socket
        try:
            with socket.create_connection((self.settings.host, self.settings.port), timeout=0.15):
                return True
        except OSError:
            return False

    def get_mysql_databases(self) -> list[str]:
        """Get user databases (excluding internal system schemas)."""
        if not self.check_mysql_status():
            return []
        try:
            if not self.mysql.connected:
                self.mysql.connect()
            all_dbs = self.mysql.databases()
            system_dbs = {"information_schema", "performance_schema", "mysql", "sys", "phpmyadmin"}
            return [db for db in all_dbs if db.lower() not in system_dbs]
        except Exception:
            return []

    def get_mysql_multi_schema(self) -> dict[str, dict[str, list[str]]]:
        """Return full table schema across all user databases."""
        details = self.get_mysql_multi_schema_details()
        result: dict[str, dict[str, list[str]]] = {}
        for db_name, tables in details.items():
            result[db_name] = {tbl: [col["name"] for col in cols] for tbl, cols in tables.items()}
        return result

    def get_mysql_multi_schema_details(self) -> dict[str, dict[str, list[dict[str, Any]]]]:
        """Return full table schema with column data types and primary key status."""
        if not self.check_mysql_status():
            return {}
        try:
            if not self.mysql.connected:
                self.mysql.connect()
            user_dbs = self.get_mysql_databases()
            if not user_dbs:
                return {}
            cursor = self.mysql.connection.cursor()
            format_strings = ",".join(["%s"] * len(user_dbs))
            cursor.execute(
                f"SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLUMN_KEY, EXTRA "
                f"FROM information_schema.COLUMNS "
                f"WHERE TABLE_SCHEMA IN ({format_strings}) ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION",
                tuple(user_dbs),
            )
            multi: dict[str, dict[str, list[dict[str, Any]]]] = {db: {} for db in user_dbs}
            for schema_name, table_name, column_name, data_type, col_key, extra in cursor:
                multi.setdefault(schema_name, {}).setdefault(table_name, []).append({
                    "name": column_name,
                    "type": (data_type or "text").upper(),
                    "is_pk": "PRI" in (col_key or ""),
                    "is_auto": "auto_increment" in (extra or "").lower(),
                })
            cursor.close()
            return multi
        except Exception:
            return {}

    def autodetect_active_engine(self) -> str:
        """Autodetect available engines: prefers live MySQL (XAMPP), falls back to SQLite."""
        if self.check_mysql_status():
            try:
                if not self.mysql.connected:
                    self.mysql.connect()
                if not self.settings.database:
                    dbs = self.get_mysql_databases()
                    if dbs:
                        self.mysql.connect(dbs[0])
                self.active_engine = "mysql"
                return "mysql"
            except Exception:
                pass
        self.active_engine = "sqlite"
        return "sqlite"

    def get_schema(self, engine: str | None = None) -> dict[str, list[str]]:
        eng = (engine or self.active_engine).lower()
        if eng == "sqlite":
            return self.sqlite.get_schema()
        if eng == "nosql":
            return self.nosql.get_schema()
        # MySQL
        if not self.mysql.connected and self.check_mysql_status():
            try:
                self.mysql.connect()
            except Exception:
                pass
        if not self.settings.database and self.mysql.connected:
            dbs = self.get_mysql_databases()
            if dbs:
                try:
                    self.mysql.connect(dbs[0])
                except Exception:
                    pass
        return self.mysql.tables

    def load_sample_data(self, engine: str | None = None) -> str:
        """Seed clean sample tables (students & courses) into the active engine."""
        eng = (engine or self.active_engine).lower()
        if eng == "nosql":
            self.nosql.insert("students", {"name": "Alex Rivera", "email": "alex@university.edu", "major": "Computer Science", "gpa": 3.85, "year": 2024})
            self.nosql.insert("students", {"name": "Beatriz Santos", "email": "beatriz@university.edu", "major": "Data Science", "gpa": 3.92, "year": 2023})
            self.nosql.insert("students", {"name": "Carlos Diaz", "email": "carlos@university.edu", "major": "Business", "gpa": 3.40, "year": 2024})
            self.nosql.insert("courses", {"code": "CS101", "title": "Intro to Programming", "credits": 3})
            self.nosql.insert("courses", {"code": "DB201", "title": "Database Systems", "credits": 4})
            return "Sample NoSQL collections 'students' and 'courses' loaded successfully!"

        if eng == "sqlite":
            stmts = [
                """CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE,
                    major TEXT,
                    gpa REAL,
                    enrollment_year INTEGER
                );""",
                """INSERT INTO students (name, email, major, gpa, enrollment_year) VALUES
                    ('Alex Rivera', 'alex@university.edu', 'Computer Science', 3.85, 2024),
                    ('Beatriz Santos', 'beatriz@university.edu', 'Data Science', 3.92, 2023),
                    ('Carlos Diaz', 'carlos@university.edu', 'Business', 3.40, 2024),
                    ('Diana Prince', 'diana@university.edu', 'Computer Science', 3.98, 2023),
                    ('Ethan Hunt', 'ethan@university.edu', 'Information Technology', 3.25, 2025);""",
                """CREATE TABLE IF NOT EXISTS courses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    credits INTEGER,
                    department TEXT
                );""",
                """INSERT INTO courses (code, title, credits, department) VALUES
                    ('CS101', 'Intro to Programming', 3, 'Computer Science'),
                    ('DB201', 'Database Systems', 4, 'Computer Science'),
                    ('DS102', 'Statistics & Probability', 3, 'Data Science');"""
            ]
            for stmt in stmts:
                try:
                    self.sqlite.execute(stmt)
                except Exception:
                    pass
            return "Sample SQLite tables 'students' and 'courses' created with 5 records and 3 courses!"
        else:
            stmts = [
                """CREATE TABLE IF NOT EXISTS students (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) UNIQUE,
                    major VARCHAR(50),
                    gpa DECIMAL(3,2),
                    enrollment_year INT
                );""",
                """INSERT INTO students (name, email, major, gpa, enrollment_year) VALUES
                    ('Alex Rivera', 'alex@university.edu', 'Computer Science', 3.85, 2024),
                    ('Beatriz Santos', 'beatriz@university.edu', 'Data Science', 3.92, 2023),
                    ('Carlos Diaz', 'carlos@university.edu', 'Business', 3.40, 2024)
                ON DUPLICATE KEY UPDATE name=VALUES(name);"""
            ]
            for stmt in stmts:
                try:
                    self.mysql.execute(stmt)
                except Exception:
                    pass
            return "Sample MySQL table 'students' created and populated!"

    def execute(self, query: str, engine: str | None = None) -> tuple[list[str] | None, list[tuple] | None, int, float, str | None]:
        """Execute on chosen engine; return (headers, rows, count, elapsed_ms, error)."""
        eng = (engine or self.active_engine).lower()
        start = time.perf_counter()
        try:
            if eng == "sqlite":
                headers, rows, count = self.sqlite.execute(query)
            elif eng == "nosql":
                headers, rows, count = self.nosql.execute_command(query)
            else:
                headers, rows, count = self.mysql.execute(query)

            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self.log_execution(ExecutionRecord(
                id=str(int(time.time() * 1000)),
                engine=eng,
                query=query,
                status="SUCCESS",
                row_count=count,
                elapsed_ms=round(elapsed_ms, 2),
                error_message=None,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            ))
            return headers, rows, count, elapsed_ms, None
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            err_msg = str(exc)
            self.log_execution(ExecutionRecord(
                id=str(int(time.time() * 1000)),
                engine=eng,
                query=query,
                status="ERROR",
                row_count=0,
                elapsed_ms=round(elapsed_ms, 2),
                error_message=err_msg,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            ))
            return None, None, 0, elapsed_ms, err_msg

    def close(self) -> None:
        self.sqlite.close()
        self.nosql.close()
