"""Optional local Ollama SQL assistant. It never executes generated SQL."""

from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .resource_guard import minimum_available_gb_for_model, require_ai_resources
from .sql_safety import inspect_sql


def _generate(prompt: str, url: str, model: str, max_tokens: int) -> str:
    """Call the local model with conservative CPU-only settings."""
    threads = max(1, min(4, (os.cpu_count() or 2) // 4))
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": 0,
        "options": {
            "num_ctx": 4096,
            "num_thread": threads,
            "num_gpu": 0,
            "num_predict": max_tokens,
            "temperature": 0,
        },
    }).encode()
    request = Request(f"{url}/api/generate", data=payload, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode()).get("response", "").strip()

def suggest_sql(question: str, database, url: str, model: str) -> str:
    require_ai_resources(minimum_available_gb_for_model(model))
    schema = "\n".join(f"{table}: {', '.join(columns)}" for table, columns in database.tables.items())
    instructions = (
        "You are a careful MySQL query writer helping a beginner. "
        "The user's wording may contain spelling or grammar mistakes. Silently correct obvious typos in your understanding, "
        "but ask a short clarification if the intended meaning is uncertain. "
        "For a clear request to find or summarize data, return exactly one SELECT statement. "
        "For an explicit request to update or delete a specific record, you may return exactly one UPDATE or DELETE statement, "
        "but it must include a precise WHERE condition copied from the request. "
        "When the user asks about an ID and the schema has a matching ID column, use that exact column. "
        "Never make an UPDATE or DELETE without a WHERE clause. Never return DROP, TRUNCATE, ALTER, or INSERT. "
        "For SQL responses, include no Markdown, code fences, explanation, or alternatives. "
        "If the user only greets you, asks a general SQL question, asks to update or delete without naming a specific row, "
        "or has not given enough details to form a safe query, return exactly `CLARIFY: ` followed by one brief helpful question or explanation. "
        "Never invent a generic query just to answer a greeting. "
        "Use only table and column names present in the schema below; never invent columns. "
        "For 'latest' or 'newest' rows, sort by a date/time column descending if one exists. "
        "If there is no date/time column, sort by the table's primary key or id column descending. "
        "Keep the requested row limit. Add a semicolon.\n\n"
        f"Database: {database.settings.database or '(not selected)'}\n"
    )
    def generate(schema_text: str) -> str:
        prompt = (
            f"{instructions}Schema:\n{schema_text or '(no schema loaded; do not invent table or column names)'}\n\n"
            f"User request: {question}\nSQL:"
        )
        return _generate(prompt, url, model, 120)

    def is_context_error(error: HTTPError) -> tuple[bool, str]:
        detail = error.read().decode("utf-8", errors="replace").strip()
        lowered = detail.lower()
        markers = ("context length", "context window", "too many tokens", "input length", "prompt is too long", "exceeds the context")
        return any(marker in lowered for marker in markers), detail or str(error.reason)

    try:
        try:
            response_text = generate(schema)
        except HTTPError as exc:
            context_error, detail = is_context_error(exc)
            if not context_error:
                raise
            # Retry with only tables that match words in the request. Keep the
            # retry small enough for a CPU-friendly 4K context window.
            terms = set(re.findall(r"[a-zA-Z_][\w$]*", question.lower()))
            relevant = [table for table in database.tables if table.lower() in terms]
            if not relevant:
                relevant = list(database.tables)[:8]
            compact_schema = "\n".join(
                f"{table}: {', '.join(database.tables[table])}" for table in relevant
            )[:3000]
            try:
                response_text = generate(compact_schema)
            except HTTPError as retry_error:
                raise RuntimeError(
                    "The request and schema are still too large for the local model. "
                    "Try asking about fewer tables or columns. Your SQLCLI session is still open."
                ) from retry_error
        if not response_text:
            raise RuntimeError("The AI returned an empty response. Try :ai reset and ask again.")
            # Small local models sometimes ignore the SQL-only instruction.
            # Remove fences/prose and show just the first SQL statement.
        clarify = re.search(r"(?im)^\s*CLARIFY:\s*(.+?)(?:\n|$)", response_text)
        if clarify:
            return "CLARIFY: " + clarify.group(1).strip()
        fenced = re.search(r"```(?:mysql|sql)?\s*(.*?)```", response_text, re.IGNORECASE | re.DOTALL)
        candidate = fenced.group(1) if fenced else response_text
        start = re.search(r"\b(?:SELECT|WITH|SHOW|DESCRIBE|EXPLAIN|DELETE|UPDATE)\b", candidate, re.IGNORECASE)
        if not start:
            raise RuntimeError("The AI did not return a SQL query. Try a shorter request or check that a database is selected.")
        query = candidate[start.start():].strip()
        if ";" in query:
            query = query.split(";", 1)[0].rstrip() + ";"
        else:
            query = query.rstrip() + ";"
        if re.match(r"\s*(?:DELETE|UPDATE)\b", query, re.IGNORECASE) and not re.search(r"\bWHERE\b", query, re.IGNORECASE):
            return "CLARIFY: I need a specific ID or condition before I can suggest a safe change."
        return query
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        if exc.code == 404:
            raise RuntimeError(
                f"Ollama could not find model '{model}'. Run `ollama list` to check installed models. "
                f"Details: {detail or exc.reason}"
            ) from exc
        raise RuntimeError(f"Ollama returned HTTP {exc.code}: {detail or exc.reason}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not reach local Ollama at {url}: {exc}") from exc


def correct_sql(sql: str, error: str, database, url: str, model: str) -> str:
    """Suggest a minimal correction for a failed SQL statement; never execute it."""
    require_ai_resources(minimum_available_gb_for_model(model))
    schema = "\n".join(f"{table}: {', '.join(columns)}" for table, columns in database.tables.items())
    prompt = (
        "You repair one failed MySQL statement for a beginner. Make only the smallest correction needed for the reported error. "
        "Preserve the exact operation, target table, conditions, values, sort order, and row limit. "
        "Fix an identifier only when the intended table or column is clear from the schema. "
        "Never remove or weaken a WHERE condition, invent a column, change a filter value, or change the SQL operation. "
        "If you cannot safely infer the intended correction, return exactly CLARIFY: followed by one short question. "
        "Otherwise return exactly one corrected SQL statement, with no Markdown or explanation.\n\n"
        f"Database: {database.settings.database or '(not selected)'}\n"
        f"Schema:\n{schema or '(no schema loaded)'}\n\n"
        f"Failed SQL:\n{sql}\n\nMySQL error:\n{error}\n\nCorrected SQL:"
    )
    try:
        response_text = _generate(prompt, url, model, 180)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Ollama returned HTTP {exc.code}: {detail or exc.reason}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not reach local Ollama at {url}: {exc}") from exc

    if not response_text:
        return "CLARIFY: I couldn't produce a safe correction."
    clarify = re.search(r"(?im)^\s*CLARIFY:\s*(.+?)(?:\n|$)", response_text)
    if clarify:
        return "CLARIFY: " + clarify.group(1).strip()
    fenced = re.search(r"```(?:mysql|sql)?\s*(.*?)```", response_text, re.IGNORECASE | re.DOTALL)
    candidate = fenced.group(1) if fenced else response_text
    start = re.search(
        r"\b(?:SELECT|WITH|SHOW|DESCRIBE|EXPLAIN|DELETE|UPDATE|INSERT|REPLACE|CREATE|ALTER|DROP|TRUNCATE|RENAME|USE)\b",
        candidate,
        re.IGNORECASE,
    )
    if not start:
        return "CLARIFY: I couldn't identify one corrected SQL statement."
    corrected = candidate[start.start():].strip()
    if not corrected.endswith(";"):
        corrected += ";"

    original_safety = inspect_sql(sql)
    corrected_safety = inspect_sql(corrected)
    if corrected_safety.multiple_statements or not corrected_safety.verb:
        return "CLARIFY: The model did not return exactly one SQL statement."
    known_verbs = {
        "SELECT", "SHOW", "DESCRIBE", "EXPLAIN", "DELETE", "UPDATE", "INSERT", "REPLACE",
        "CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME", "USE",
    }
    if original_safety.verb in known_verbs:
        if corrected_safety.verb != original_safety.verb:
            return "CLARIFY: The suggested SQL changes the type of operation."
    else:
        first_word = re.match(r"\s*([A-Za-z]+)", sql)
        if not first_word or SequenceMatcher(None, first_word.group(1).upper(), corrected_safety.verb).ratio() < 0.7:
            return "CLARIFY: The suggested SQL may change the type of operation."
    if corrected_safety.missing_where:
        return "CLARIFY: The correction would change data without a WHERE condition."
    return corrected
