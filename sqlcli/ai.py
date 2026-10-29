"""Optional local Ollama SQL assistant. It never executes generated SQL."""

from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .resource_guard import require_ai_resources

def suggest_sql(question: str, database, url: str, model: str) -> str:
    require_ai_resources()
    schema = "\n".join(f"{table}: {', '.join(columns)}" for table, columns in database.tables.items())
    instructions = (
        "You are a careful MySQL query writer helping a beginner. "
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
    # Keep local inference conservative for CPU-only laptops: use a short
    # context, limit worker threads, force CPU, and release the model after use.
    threads = max(1, min(4, (os.cpu_count() or 2) // 4))
    def generate(schema_text: str) -> str:
        prompt = (
            f"{instructions}Schema:\n{schema_text or '(no schema loaded; do not invent table or column names)'}\n\n"
            f"User request: {question}\nSQL:"
        )
        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": 0,
            "options": {
                "num_ctx": 4096,
                "num_thread": threads,
                "num_gpu": 0,
                "num_predict": 120,
                "temperature": 0,
            },
        }).encode()
        request = Request(f"{url}/api/generate", data=payload, headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode()).get("response", "").strip()

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
