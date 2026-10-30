"""Interactive SQL Workbench terminal."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from tabulate import tabulate

from . import __version__
from .ai import correct_sql, suggest_sql
from .completion import SQLCompleter
from .config import load_settings
from .connection import Database
from .ollama_service import (
    ensure_ready,
    pull as pull_ollama,
    reset_model as reset_ollama_model,
    start as start_ollama,
    status as ollama_status,
)
from .plugins import PluginRegistry, load_plugins
from .sql_safety import inspect_sql

STYLE = Style.from_dict({
    "prompt": "ansigreen bold",
    "database": "ansicyan bold",
    "bottom-toolbar": "bg:#202a34 #c8d3dc",
})
QUESTION_START = re.compile(r"^(?:what|why|how|can you|could you|please|hello|hi|hey|tell me)\b", re.IGNORECASE)


def _safe_csv_cell(value):
    """Keep untrusted text from becoming a spreadsheet formula on open."""
    if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _offer_ai_correction(sql, error, database, settings, session, ai_enabled: bool) -> None:
    """Offer a reviewed SQL repair for common MySQL syntax/name errors."""
    if not ai_enabled or getattr(error, "errno", None) not in {1052, 1054, 1064, 1146}:
        return
    try:
        ensure_ready(settings)
        correction = correct_sql(
            sql, str(error), database, settings.ollama_url, settings.ollama_model
        )
    except Exception as correction_error:
        print(f"AI correction is unavailable: {correction_error}")
        return
    if correction.startswith("CLARIFY:"):
        print("AI could not safely correct that SQL: " + correction.removeprefix("CLARIFY:").strip())
        return

    print("\nAI correction suggestion (not run yet):")
    print(correction)
    safety = inspect_sql(correction)
    if safety.multiple_statements or safety.missing_where:
        print("Blocked for safety: the suggested query failed SQLCLI's safety checks and was not run.")
        return
    if safety.requires_confirmation:
        print("Warning: this corrected statement can change or remove database data/schema.")
    try:
        answer = session.prompt("Type YES to run this corrected query, or anything else to cancel: ").strip()
    except KeyboardInterrupt:
        answer = ""
    if answer != "YES":
        print("Correction cancelled. No corrected query was run.")
        return

    try:
        headers, rows, count = database.execute(correction)
        if headers:
            print(tabulate(rows, headers=headers, tablefmt="rounded_grid", showindex=False))
            print_formatted_text(HTML(f"\n<ansigray>{len(rows)} row(s)</ansigray>"))
        else:
            print(f"Corrected query OK, {count} row(s) affected.")
            if safety.verb in {"CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME"}:
                database.refresh_schema()
                try:
                    database.refresh_databases()
                except Exception:
                    pass
    except Exception as corrected_error:
        print(f"The corrected query still failed: {corrected_error}")


def print_banner(settings, database, plugin_count: int) -> None:
    state = "<ansigreen>● connected</ansigreen>" if database.connected else "<ansiyellow>○ offline</ansiyellow>"
    target = f"{settings.host}:{settings.port}"
    if settings.database:
        target += f" / {settings.database}"
    print_formatted_text(HTML(f"\n<ansicyan><b>SQLCLI</b></ansicyan>  <ansigray>Workbench {__version__}</ansigray>"))
    print_formatted_text(HTML(f"{state}  <ansigray>{target}</ansigray>"))
    print_formatted_text(HTML(f"<ansigray>Tab suggestions  ·  :help commands  ·  :quit exit  ·  {plugin_count} plugin(s)</ansigray>\n"))


def print_help() -> None:
    print("""SQLCLI commands:
  :connect [database]   Connect to XAMPP MySQL or select a database
  :use <database>       Switch database
  :databases            List databases
  :tables               List tables in the current database
  :describe <table>     Show a table's columns, types, and keys
  :sample <table> [n]   Preview up to 100 rows (default: 10)
  :count <table>        Count rows in a table
  :export <file.csv> SELECT ...
                        Save a read-only SELECT result as a new CSV file
  :refresh              Refresh database, table, and column suggestions
  :ai on|off|reset      Enable, disable, or reset the local AI model
  :ollama start         Start Ollama and connect the configured model
  :ollama status        Check Ollama and model connection
  :ollama pull          Download the configured model
  :ask <request>        Suggest SQL using local Ollama (never executes it)
  :plugins              Show loaded plugins
  :help                 Show this help
  :quit                 Exit

Type SQL and press Enter; statements run when terminated with a semicolon.
Tab shows suggestions. Up/Down navigates suggestions and command history.""")


def main() -> None:
    settings = load_settings()
    database = Database(settings)
    plugins = PluginRegistry()
    load_plugins(plugins)
    try:
        database.connect()
    except Exception as exc:
        print_formatted_text(HTML("<ansiyellow>MySQL is offline.</ansiyellow> Start MySQL in XAMPP, then enter <b>:connect</b>."))
        print("If it still cannot connect, check the settings in .env.\n")

    print_banner(settings, database, len(plugins.names))

    session = PromptSession(
        completer=SQLCompleter(database, plugins),
        complete_while_typing=True,
        history=FileHistory(str(Path.home() / ".sqlcli_history")),
        style=STYLE,
        prompt_continuation="... ",
        bottom_toolbar=lambda: HTML(
            "  <b>Enter</b> new line  ·  statement runs after <b>;</b>  ·  <b>Ctrl+C</b> cancel"
        ),
    )
    buffer = ""
    ai_enabled = settings.ai_enabled
    try:
        while True:
            db = settings.database or "no database"
            try:
                state = " (SQL continues)" if buffer else ""
                line = session.prompt([
                    ("class:prompt", "sqlcli "),
                    ("class:database", f"{db}{state} "),
                    ("", "› "),
                ])
            except EOFError:
                break
            except KeyboardInterrupt:
                buffer = ""
                print("^C")
                continue
            stripped = line.strip()
            if stripped.startswith(":"):
                if buffer:
                    print("Cancelled the unfinished SQL line so I can run your command.")
                    buffer = ""
                command, _, argument = stripped[1:].partition(" ")
                command = command.lower()
                try:
                    if command in {"quit", "exit", "q"}:
                        break
                    elif command in {"help", "h"}:
                        print_help()
                    elif command == "connect":
                        database.connect(argument.strip() or None)
                        print_formatted_text(HTML(f"<ansigreen>Connected</ansigreen>  {settings.host}:{settings.port}" + (f" / {settings.database}" if settings.database else "")))
                    elif command == "use":
                        if not argument.strip():
                            print("Usage: :use <database>")
                        else:
                            database.connect(argument.strip())
                            print(f"Using database {settings.database}")
                    elif command == "databases":
                        print("\n".join(database.databases()))
                    elif command == "tables":
                        if not settings.database:
                            print("Select a database first with :use <database>.")
                        else:
                            print("\n".join(database.tables) or "No tables found.")
                    elif command in {"describe", "columns"}:
                        if not argument.strip():
                            print("Usage: :describe <table> (example: :describe users)")
                        else:
                            columns = database.describe_table(argument.strip().strip("`"))
                            print(tabulate(
                                columns,
                                headers=["Column", "Type", "Nullable", "Key", "Default", "Extra"],
                                tablefmt="rounded_grid",
                            ))
                    elif command == "sample":
                        parts = argument.split()
                        if not parts:
                            print("Usage: :sample <table> [number of rows]")
                        else:
                            limit = int(parts[1]) if len(parts) > 1 else 10
                            headers, rows = database.sample_table(parts[0].strip("`"), limit)
                            print(tabulate(rows, headers=headers, tablefmt="rounded_grid", showindex=False))
                            print(f"\nShowing {len(rows)} row(s).")
                    elif command == "count":
                        if not argument.strip():
                            print("Usage: :count <table> (example: :count records)")
                        else:
                            table = argument.strip().strip("`")
                            total = database.count_table(table)
                            print(f"{table} contains {total:,} row(s).")
                    elif command == "export":
                        parts = argument.strip().split(maxsplit=1)
                        if len(parts) != 2:
                            print("Usage: :export <file.csv> SELECT ... (example: :export records.csv SELECT * FROM records;)")
                        else:
                            filename, query = parts
                            query = query.strip()
                            if query.endswith(";"):
                                query = query[:-1].rstrip()
                            if not re.match(r"^SELECT\b", query, re.IGNORECASE) or ";" in query:
                                raise RuntimeError("Export accepts one read-only SELECT statement only.")
                            if re.search(r"\bINTO\s+(?:OUTFILE|DUMPFILE)\b|\bFOR\s+UPDATE\b", query, re.IGNORECASE):
                                raise RuntimeError("This SELECT includes a file-write or locking clause; remove it before exporting.")
                            headers, rows, _ = database.execute(query)
                            if not headers:
                                raise RuntimeError("The SELECT did not return a result set to export.")
                            output = Path(filename).expanduser()
                            with output.open("x", newline="", encoding="utf-8-sig") as file:
                                writer = csv.writer(file)
                                writer.writerow(headers)
                                writer.writerows(
                                    [_safe_csv_cell(value) for value in row]
                                    for row in (rows or [])
                                )
                            print(f"Saved {len(rows or [])} row(s) to {output.resolve()}")
                    elif command == "refresh":
                        database.refresh_schema()
                        try:
                            database.refresh_databases()
                        except Exception:
                            pass  # Schema suggestions still work if SHOW DATABASES is restricted.
                        print(
                            f"Loaded {len(database.tables)} tables and "
                            f"{len(database.database_names)} database name(s) for autocomplete."
                        )
                    elif command == "ai":
                        mode = argument.strip().lower()
                        if mode == "reset":
                            print(reset_ollama_model(settings))
                            continue
                        if mode not in {"on", "off", "true", "false", "1", "0"}:
                            print("Usage: :ai on | :ai off | :ai reset")
                            continue
                        ai_enabled = mode in {"on", "true", "1"}
                        print(f"Local AI assistance {'enabled' if ai_enabled else 'disabled'}.")
                    elif command == "ollama":
                        action = argument.strip().lower()
                        if action == "start":
                            print(start_ollama(settings))
                        elif action == "status":
                            print(ollama_status(settings))
                        elif action == "pull":
                            print(f"Downloading {settings.ollama_model} into the configured Ollama model folder...")
                            print(pull_ollama(settings))
                        else:
                            print("Usage: :ollama start | status | pull")
                    elif command == "ask":
                        if not ai_enabled:
                            print("Enable local assistance first with :ai on.")
                        elif not argument.strip():
                            print("Usage: :ask <what SQL should do>")
                        else:
                            ensure_ready(settings)
                            proposal = suggest_sql(argument.strip(), database, settings.ollama_url, settings.ollama_model)
                            if proposal.startswith("CLARIFY:"):
                                print(proposal.removeprefix("CLARIFY:").strip())
                                print("\nTry :ask followed by a specific request.\n")
                                continue
                            print_formatted_text(HTML(
                                f"\n<ansicyan><b>SQL suggestion</b></ansicyan>  "
                                f"<ansigray>{settings.database or 'no database selected'}</ansigray>"
                            ))
                            print(proposal)
                            print("Review it, then copy and paste it to run. Changes require confirmation.\n")
                    elif command == "plugins":
                        if plugins.names:
                            print("Loaded plugins: " + ", ".join(plugins.names))
                            if plugins.commands:
                                print("Plugin commands: " + ", ".join(f":{name}" for name in plugins.commands))
                            else:
                                print("These plugins add no commands; press Tab while typing SQL to try their suggestions.")
                        else:
                            print("No plugins loaded. Add trusted Python plugins under ./plugins.")
                    elif command in plugins.commands:
                        plugins.commands[command](argument, database)
                    else:
                        print(f"Unknown command :{command}. Use :help.")
                except Exception as exc:
                    print(f"Error: {exc}")
                continue

            if QUESTION_START.match(stripped):
                if buffer:
                    print("Cancelled the unfinished SQL line; your question was not sent to the database.")
                    buffer = ""
                print("That looks like a question, not SQL. Start it with :ask, for example:")
                print(":ask show the latest 10 records")
                print("For SQL help, add a colon before :ask.\n")
                continue

            was_continuing = bool(buffer)
            buffer += ("\n" if buffer else "") + line
            if not buffer.strip():
                continue
            if not buffer.rstrip().endswith(";"):
                if not was_continuing:
                    print_formatted_text(HTML(
                        "<ansiyellow>Waiting for ;</ansiyellow> SQL runs after a semicolon. "
                        "Example: <b>USE your_database_name;</b> Keep typing, or press Ctrl+C to cancel."
                    ))
                continue
            try:
                safety = inspect_sql(buffer.strip())
                if safety.multiple_statements:
                    print("SQLCLI runs one statement at a time. Split this into separate commands; no SQL was run.")
                    buffer = ""
                    continue
                if safety.missing_where:
                    print("Blocked for safety: UPDATE and DELETE need a WHERE condition. No data was changed.")
                    buffer = ""
                    continue
                if safety.requires_confirmation:
                    print("Warning: this statement can change or remove database data/schema.")
                    try:
                        confirmation = session.prompt("Type YES to run it, or anything else to cancel: ").strip()
                    except KeyboardInterrupt:
                        confirmation = ""
                    if confirmation != "YES":
                        print("Cancelled. No changes were made.")
                        buffer = ""
                        continue
                headers, rows, count = database.execute(buffer.strip())
                if headers:
                    print(tabulate(rows, headers=headers, tablefmt="rounded_grid", showindex=False))
                    print_formatted_text(HTML(f"\n<ansigray>{len(rows)} row(s)</ansigray>"))
                else:
                    print(f"Query OK, {count} row(s) affected.")
                    if safety.verb in {"CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME"}:
                        database.refresh_schema()
                        try:
                            database.refresh_databases()
                        except Exception:
                            pass  # Keep command completion working with restricted database visibility.
            except Exception as exc:
                print(f"SQL error: {exc}")
                print("Tip: check the table/column spelling and make sure the statement ends with ;")
                _offer_ai_correction(buffer.strip(), exc, database, settings, session, ai_enabled)
            buffer = ""
    finally:
        database.close()
        print("Goodbye.")


if __name__ == "__main__":
    main()
