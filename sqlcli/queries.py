"""Per-user storage for named SQL snippets."""

from __future__ import annotations

import json
import re
from pathlib import Path


def _path() -> Path:
    return Path.home() / ".sqlcli_queries.json"


def load_queries() -> dict[str, str]:
    path = _path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read saved queries: {exc}") from exc
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
        raise RuntimeError("Saved query file has an invalid format.")
    return data


def save_query(name: str, sql: str) -> None:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", name):
        raise RuntimeError("Query name must start with a letter and contain only letters, numbers, _ or - (max 40).")
    if not sql.strip() or ";" in sql.rstrip().removesuffix(";"):
        raise RuntimeError("Save one SQL statement at a time.")
    queries = load_queries()
    queries[name] = sql.strip().removesuffix(";") + ";"
    path = _path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(queries, indent=2), encoding="utf-8")
    temporary.replace(path)


def get_query(name: str) -> str:
    try:
        return load_queries()[name]
    except KeyError as exc:
        raise RuntimeError(f"No saved query named '{name}'. Use :saved to list saved queries.") from exc
