"""MySQL connection and schema metadata helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import mysql.connector
from mysql.connector import MySQLConnection

from .config import Settings


@dataclass
class Database:
    settings: Settings
    connection: MySQLConnection | None = None
    tables: dict[str, list[str]] = field(default_factory=dict)
    database_names: list[str] = field(default_factory=list)

    @property
    def connected(self) -> bool:
        return bool(self.connection and self.connection.is_connected())

    def connect(self, database: str | None = None) -> None:
        self.close()
        target = database if database is not None else self.settings.database
        options = {
            "host": self.settings.host,
            "port": self.settings.port,
            "user": self.settings.user,
            "password": self.settings.password,
            "connection_timeout": 5,
            "autocommit": True,
        }
        if target:
            options["database"] = target
        self.connection = mysql.connector.connect(**options)
        self.settings.database = target
        self.refresh_schema()
        # Cache once at connection time so live completion never sends a query
        # for every character the user types. Some restricted accounts cannot
        # list databases, so that optional cache must not break the connection.
        try:
            self.refresh_databases()
        except mysql.connector.Error:
            self.database_names.clear()

    def close(self) -> None:
        if self.connection and self.connection.is_connected():
            self.connection.close()
        self.connection = None
        self.tables.clear()
        self.database_names.clear()

    def refresh_schema(self) -> None:
        if not self.connected or not self.settings.database:
            self.tables.clear()
            return
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME, ORDINAL_POSITION",
                (self.settings.database,),
            )
            schema: dict[str, list[str]] = {}
            for table, column in cursor:
                schema.setdefault(table, []).append(column)
            self.tables = schema
        finally:
            cursor.close()

    def databases(self) -> list[str]:
        self.refresh_databases()
        return list(self.database_names)

    def refresh_databases(self) -> None:
        if not self.connected:
            self.database_names.clear()
            return
        cursor = self.connection.cursor()
        try:
            cursor.execute("SHOW DATABASES")
            self.database_names = [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()

    def describe_table(self, table: str) -> list[tuple]:
        if not self.connected:
            raise RuntimeError("Not connected. Start MySQL and use :connect first.")
        if not self.settings.database:
            raise RuntimeError("Choose a database first with :use <database>.")
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                "SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_DEFAULT, EXTRA "
                "FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                "ORDER BY ORDINAL_POSITION",
                (self.settings.database, table),
            )
            rows = cursor.fetchall()
            if not rows:
                raise RuntimeError(f"Table '{table}' was not found in database '{self.settings.database}'.")
            return rows
        finally:
            cursor.close()

    def _checked_table(self, table: str) -> str:
        if not self.connected:
            raise RuntimeError("Not connected. Start MySQL and use :connect first.")
        if not self.settings.database:
            raise RuntimeError("Choose a database first with :use <database>.")
        if table not in self.tables:
            raise RuntimeError(f"Table '{table}' is not in the current database. Use :tables to see available tables.")
        return f"`{table.replace('`', '``')}`"

    def sample_table(self, table: str, limit: int = 10) -> tuple[list[str], list[tuple]]:
        if not 1 <= limit <= 100:
            raise RuntimeError("Preview limit must be between 1 and 100 rows.")
        quoted_table = self._checked_table(table)
        headers, rows, _ = self.execute(f"SELECT * FROM {quoted_table} LIMIT {limit}")
        return headers or [], rows or []

    def count_table(self, table: str) -> int:
        quoted_table = self._checked_table(table)
        _, rows, _ = self.execute(f"SELECT COUNT(*) FROM {quoted_table}")
        return int(rows[0][0])

    def execute(self, sql: str) -> tuple[list[str] | None, list[tuple] | None, int]:
        if not self.connected:
            raise RuntimeError("Not connected. Use :connect first.")
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql)
            # MySQL's USE statement changes the server session, but the
            # application settings also drive the prompt and autocomplete.
            selected = re.fullmatch(r"\s*USE\s+`?([\w$]+)`?\s*;?\s*", sql, re.IGNORECASE)
            if selected:
                self.settings.database = selected.group(1)
                self.refresh_schema()
            if cursor.with_rows:
                return [column[0] for column in cursor.description], cursor.fetchall(), cursor.rowcount
            return None, None, cursor.rowcount
        finally:
            cursor.close()
