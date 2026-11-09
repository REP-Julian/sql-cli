"""Interactive SQL Workbench terminal."""

from __future__ import annotations

import csv
import json
import re
import sys
import time
from pathlib import Path

from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.filters import has_completions
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from tabulate import tabulate

from . import __version__
from .ai import chat_response, correct_sql, suggest_sql
from .autopilot import run_autopilot
from .autosuggest import SQLAutoSuggest
from .chat_memory import add_memory, load_memories, remove_memory
from .clipboard import SystemClipboard, get_clipboard_text, set_clipboard_text
from .completion import SQLCompleter
from .config import load_settings
from .connection import Database
from .diagnostics import analyze_error, format_cli_error_box
from .knowledge import format_topic_card, list_topics, lookup_topic
from .multi_engine import MultiEngineManager, NoSQLEngine, SQLiteEngine
from .ollama_service import (
    ensure_ready,
    pull as pull_ollama,
    reset_model as reset_ollama_model,
    start as start_ollama,
    status as ollama_status,
)
from .plugins import PluginRegistry, load_plugins
from .queries import get_query, load_queries, save_query
from .server import start_studio_server
from .sql_safety import inspect_sql

STYLE = Style.from_dict({
    "prompt": "ansigreen bold",
    "database": "ansicyan bold",
    "bottom-toolbar": "bg:#202a34 #c8d3dc",
})


def print_text(formatted_obj: Any, **kwargs: Any) -> None:
    """Print formatted HTML text with plain-text fallback if no Win32 console buffer."""
    try:
        from prompt_toolkit import print_formatted_text
        print_formatted_text(formatted_obj, **kwargs)
    except Exception:
        raw = getattr(formatted_obj, "value", str(formatted_obj))
        clean = re.sub(r"<[^>]+>", "", str(raw))
        clean = clean.replace("\u25cf", "*").replace("\u25cb", "o").replace("\u2713", "[OK]")
        try:
            print(clean, **kwargs)
        except UnicodeEncodeError:
            encoding = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
            clean_bytes = clean.encode(encoding, errors="replace")
            print(clean_bytes.decode(encoding), **kwargs)


QUESTION_START = re.compile(r"^(?:what|why|how|can you|could you|please|hello|hi|hey|tell me)\b", re.IGNORECASE)


def _safe_csv_cell(value):
    """Keep untrusted text from becoming a spreadsheet formula on open."""
    if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _is_complete_statement(text: str) -> bool:
    """Return True if text is empty, a colon command, or ends with a semicolon."""
    stripped = text.strip()
    if not stripped or stripped.startswith(":"):
        return True
    clean = re.sub(r"--[^\n]*$", "", stripped).strip()
    clean = re.sub(r"/\*.*?\*/$", "", clean, flags=re.DOTALL).strip()
    return clean.endswith(";")


def save_output_to_file(path_str: str, headers: list[str] | None, rows: list[tuple] | None) -> None:
    """Save query results as CSV, JSON, or formatted table text."""
    if not headers or rows is None:
        raise RuntimeError("No recent query output to save. Run a SELECT query first.")
    dest = Path(path_str).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    suffix = dest.suffix.lower()
    if suffix == ".csv":
        with dest.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow(headers)
            writer.writerows([[_safe_csv_cell(value) for value in row] for row in rows])
    elif suffix == ".json":
        records = [dict(zip(headers, row)) for row in rows]
        dest.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
    else:
        dest.write_text(tabulate(rows, headers=headers, tablefmt="rounded_grid"), encoding="utf-8")
    print(f"Saved {len(rows)} row(s) to {dest.resolve()}")


def save_sql_to_file(path_str: str, sql: str) -> None:
    """Save an SQL statement into a file on disk."""
    if not sql.strip():
        raise RuntimeError("No SQL statement provided or available to save.")
    dest = Path(path_str).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    formatted = sql.strip()
    if not formatted.rstrip().endswith(";"):
        formatted += ";"
    dest.write_text(formatted + "\n", encoding="utf-8")
    print(f"Saved SQL statement to {dest.resolve()}")


def _offer_ai_correction(sql, error, database, settings, session, ai_enabled: bool) -> None:
    """Offer a reviewed SQL repair for common MySQL syntax/name/db errors."""
    if not ai_enabled or getattr(error, "errno", None) not in {1046, 1049, 1050, 1051, 1052, 1054, 1062, 1064, 1146, 1364}:
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
        answer = session.prompt("Type YES to run this corrected query, or anything else to cancel: ").strip().lower()
    except KeyboardInterrupt:
        answer = ""
    if answer not in {"yes", "y"}:
        print("Correction cancelled. No corrected query was run.")
        return

    try:
        headers, rows, count = database.execute(correction)
        if headers:
            print(tabulate(rows, headers=headers, tablefmt="rounded_grid", showindex=False))
            print_text(HTML(f"\n<ansigray>{len(rows)} row(s)</ansigray>"))
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
    print_text(HTML(f"\n<ansicyan><b>SQLCLI</b></ansicyan>  <ansigray>Workbench {__version__}</ansigray>"))
    print_text(HTML(f"{state}  <ansigray>{target}</ansigray>  <ansigreen>● Terminal Studio ready</ansigreen>"))
    print_text(HTML(
        "<ansigray>Type :studio for full Terminal Studio  ·  Shift+Tab new line  ·  Ctrl+V paste  ·  :engine [mysql|sqlite|nosql]  ·  :help</ansigray>\n"
    ))


def print_help() -> None:
    print("""SQLCLI commands:
  :gui, :desktop        Launch Native Desktop Studio (PyQt6 window)
  :studio, :tui         Launch spacious Terminal Studio Dashboard (inside terminal)
  :engine [type]        Switch active engine: mysql, sqlite, or nosql
  :sqlite [path]        Switch to local zero-config SQLite engine
  :nosql [path]         Switch to local JSON document store (MongoDB-style)
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
  :history [n]          Show recent commands (default: 20, max: 100)
  :find <text>          Find tables and columns by name
  :paste [run]          Paste SQL from system clipboard (or press Ctrl+V)
  :copy [last|sql]      Copy last query or custom text to clipboard
  :save <name> [SQL]    Save a query (uses last query if SQL omitted)
  :save file <file.sql> [SQL]
                        Save an SQL statement or last query to a .sql file
  :save output <file.csv|json|txt>
                        Save the last query's result set to a file
  :saved                List saved SQL statements
  :run <name>           Run a saved statement through normal safety checks
  :autopilot <goal>     Natural language SQL assistant (generates & executes queries)
  :learn [topic]        Browse W3Schools SQL tutorials, syntax, & examples
  :ai on|off|reset      Enable, disable, or reset the local AI model
  :ollama start         Start Ollama and connect the configured model
  :ollama status        Check Ollama and model connection
  :ollama pull          Download the configured model
  :ask <request>        Suggest SQL using local Ollama (never executes it)
  :chat <message>       Chat with the local AI
  :chat remember <text> Save a detail for future chat sessions
  :chat memory          List saved chat details
  :chat forget <n|all>  Remove saved chat details
  :chat reset           Clear this run's chat history
  :plugins              Show loaded plugins
  :help                 Show this help
  :quit                 Exit

Multiline editing:
  Enter                 Creates a new line while statement is open; runs when ended with ;
  Shift+Tab             Inserts a new line with 4-space indent anytime
  Alt+Enter             Forces execution of the statement immediately
  Ctrl+V                Pastes from system clipboard
  Up/Down               Moves between lines (or history at edge)
  Ctrl+C                Cancels the current input""")


def print_history(history, argument: str = "") -> None:
    """Display recent prompt entries with stable session-local numbering."""
    try:
        limit = int(argument) if argument else 20
    except ValueError as exc:
        raise RuntimeError("Usage: :history [number from 1 to 100]") from exc
    if not 1 <= limit <= 100:
        raise RuntimeError("History limit must be between 1 and 100.")
    entries = history.get_strings()
    if not entries:
        print("No command history yet.")
        return
    recent = entries[-limit:]
    start = len(entries) - len(recent) + 1
    for index, entry in enumerate(recent, start):
        print(f"{index:>4}  {' '.join(entry.splitlines())}")


def find_schema(database, term: str) -> None:
    """Find matching tables and columns in the loaded schema."""
    needle = term.strip().strip("\"").lower()
    if not needle:
        raise RuntimeError("Usage: :find <table or column text>")
    matches = []
    for table, columns in database.tables.items():
        if needle in table.lower():
            matches.append(("table", table, ""))
        for column in columns:
            if needle in column.lower():
                matches.append(("column", table, column))
    if not matches:
        print(f"No table or column names contain '{needle}'.")
        return
    print(tabulate(matches, headers=["Type", "Table", "Column"], tablefmt="rounded_grid"))


def print_rows_paged(session, headers, rows, page_size: int = 20) -> None:
    """Display query results in small pages so large results stay navigable."""
    rows = rows or []
    if not rows:
        print(tabulate([], headers=headers, tablefmt="rounded_grid"))
        print("\n0 row(s)")
        return
    for start in range(0, len(rows), page_size):
        page = rows[start:start + page_size]
        print(tabulate(page, headers=headers, tablefmt="rounded_grid", showindex=False))
        print(f"\nRows {start + 1}-{start + len(page)} of {len(rows)}")
        if start + page_size < len(rows):
            try:
                answer = session.prompt("Enter for next page, q to stop: ").strip().lower()
            except KeyboardInterrupt:
                print("\nPaging stopped.")
                return
            if answer == "q":
                return


def execute_statement(
    sql: str,
    database: Database,
    settings: Any,
    session: Any,
    ai_enabled: bool,
    engine_manager: MultiEngineManager | None = None,
) -> tuple[list[str] | None, list[tuple] | None, int] | None:
    """Apply safety checks, run one statement, and report its elapsed time."""
    active_engine = (engine_manager.active_engine if engine_manager else "mysql").lower()
    safety = None

    if active_engine == "mysql":
        safety = inspect_sql(sql)
        if safety.multiple_statements:
            print("SQLCLI runs one statement at a time. Split this into separate commands; no SQL was run.")
            return None
        if safety.missing_where:
            print("Blocked for safety: UPDATE and DELETE need a WHERE condition. No data was changed.")
            return None
        if safety.requires_confirmation:
            print("Warning: this statement can change or remove database data/schema.")
            try:
                confirmation = session.prompt("Type YES to run it, or anything else to cancel: ").strip().lower()
            except KeyboardInterrupt:
                confirmation = ""
            if confirmation not in {"yes", "y"}:
                print("Cancelled. No changes were made.")
                return None

    started = time.perf_counter()
    try:
        if engine_manager:
            headers, rows, count, elapsed_ms, err = engine_manager.execute(sql)
            if err:
                raise RuntimeError(err)
            elapsed = elapsed_ms / 1000.0
        else:
            headers, rows, count = database.execute(sql)
            elapsed = time.perf_counter() - started

        if headers:
            print_rows_paged(session, headers, rows)
            print_text(HTML(f"\n<ansigray>{len(rows or [])} row(s) in {elapsed:.3f}s [{active_engine.upper()}]</ansigray>"))
        else:
            print(f"Query OK, {count} row(s) affected in {elapsed:.3f}s [{active_engine.upper()}].")
            if active_engine == "mysql" and safety and safety.verb in {"CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME"}:
                database.refresh_schema()
                try:
                    database.refresh_databases()
                except Exception:
                    pass
        return headers, rows, count
    except Exception as exc:
        schema = engine_manager.get_schema() if engine_manager else getattr(database, "tables", {})
        diag = analyze_error(sql, exc, schema, engine=active_engine)
        print(format_cli_error_box(diag, sql))
        if active_engine == "mysql":
            _offer_ai_correction(sql, exc, database, settings, session, ai_enabled)
        return None


def main() -> None:
    settings = load_settings()
    if "--help" in sys.argv or "-h" in sys.argv:
        print("""SQLCLI - Multi-Engine Database Desktop Studio & Workbench

Usage:
  sqlcli                       Launch Native Desktop Studio (PyQt6 GUI)
  sqlcli --tui, --terminal     Launch full Terminal Studio (TUI)
  sqlcli --prompt, --legacy    Launch classic interactive REPL
  sqlcli --web                 Start local SQLite Web Dashboard
  sqlcli --help, -h            Show this help message
  sqlcli --version, -v         Show version number

Desktop Studio Features:
  * Full OS-native scrollbars (vertical & horizontal mouse draggable)
  * Resizable split panels (drag borders to resize editor and tables)
  * 300+ topic W3Schools SQL Tutor syllabus with one-click editor loader
  * Interactive schema inspector with double-click query generator
  * Error diagnostics HUD with instant one-click [Auto-Fix & Rerun]
  * Tabular results spreadsheet grid with click-to-sort and column drag-resize
  * 100% offline - SQLite, local NoSQL, XAMPP MySQL, and rule-based Autopilot
""")
        return

    if "--version" in sys.argv or "-v" in sys.argv:
        print(f"sqlcli version {__version__}")
        return

    database = Database(settings)
    engine_manager = MultiEngineManager(settings, database)

    # 1. Web Studio mode
    if "--web" in sys.argv or "--browser" in sys.argv:
        try:
            port = 8080
            for idx, arg in enumerate(sys.argv):
                if arg in {"--port", "-p"} and idx + 1 < len(sys.argv):
                    port = int(sys.argv[idx + 1])
            start_studio_server(engine_manager, port=port, open_browser=True)
            return
        except Exception as exc:
            print(f"Failed to start web server: {exc}")
            return

    # 2. Terminal Studio mode
    if "--tui" in sys.argv or "--terminal" in sys.argv:
        try:
            from .tui import start_terminal_studio
            start_terminal_studio(engine_manager, settings, database)
            return
        except Exception as exc:
            print(f"Failed to launch Terminal Studio: {exc}")

    # 3. Classic Interactive Prompt mode
    if "--prompt" in sys.argv or "--legacy" in sys.argv:
        pass
    else:
        # Default: Launch Native PyQt6 Desktop Studio
        try:
            from .gui import start_gui_app
            start_gui_app(engine_manager, settings, database)
            return
        except Exception:
            # Fallback to Terminal Studio if graphical environment unavailable
            try:
                from .tui import start_terminal_studio
                start_terminal_studio(engine_manager, settings, database)
                return
            except Exception:
                pass

    plugins = PluginRegistry()
    load_plugins(plugins)
    try:
        database.connect()
    except Exception as exc:
        print_text(HTML("<ansiyellow>MySQL is offline.</ansiyellow> Start MySQL in XAMPP, then enter <b>:connect</b> (or use :engine sqlite)."))
        print("If it still cannot connect, check the settings in .env.\n")

    print_banner(settings, database, len(plugins.names))

    bindings = KeyBindings()

    @bindings.add("s-tab")
    def _shift_tab(event):
        """Insert newline with 4-space indent on Shift+Tab."""
        event.current_buffer.insert_text("\n    ")

    @bindings.add("c-v")
    def _paste(event):
        """Paste system clipboard text at cursor on Ctrl+V."""
        text = get_clipboard_text()
        if text:
            event.current_buffer.insert_text(text)

    @bindings.add("escape", "enter")
    def _force_submit(event):
        """Force submit buffer on Alt+Enter."""
        event.current_buffer.validate_and_handle()

    @bindings.add("enter", filter=~has_completions)
    def _smart_enter(event):
        """Submit on semicolon or colon command; otherwise insert a newline with indent."""
        buf = event.current_buffer
        text = buf.text.strip()
        if _is_complete_statement(text):
            buf.validate_and_handle()
        else:
            buf.insert_text("\n    ")

    def _prompt_continuation(width, line_number, is_soft_wrap):
        return [("class:database", "... ")]

    session_output = None
    try:
        from prompt_toolkit.output.defaults import create_output
        session_output = create_output()
    except Exception:
        from prompt_toolkit.output import DummyOutput
        session_output = DummyOutput()

    session = PromptSession(
        output=session_output,
        completer=SQLCompleter(database, plugins),
        complete_while_typing=True,
        auto_suggest=SQLAutoSuggest(database),
        multiline=True,
        key_bindings=bindings,
        clipboard=SystemClipboard(),
        history=FileHistory(str(Path.home() / ".sqlcli_history")),
        style=STYLE,
        prompt_continuation=_prompt_continuation,
        bottom_toolbar=lambda: HTML(
            f"  <b>Engine:</b> {engine_manager.active_engine.upper()}  ·  <b>:dashboard</b> SQLite Studio UI  ·  <b>Enter</b> run on <b>;</b>  ·  <b>Shift+Tab</b> new line  ·  <b>Ctrl+V</b> paste"
        ),
    )
    last_sql = ""
    last_headers: list[str] | None = None
    last_rows: list[tuple] | None = None
    pending_default = ""
    ai_enabled = settings.ai_enabled
    chat_history: list[dict[str, str]] = []
    try:
        while True:
            if engine_manager.active_engine == "sqlite":
                eng_tag = "sqlite"
                db_label = Path(engine_manager.sqlite.db_path).name
            elif engine_manager.active_engine == "nosql":
                eng_tag = "nosql"
                db_label = Path(engine_manager.nosql.db_path).name
            else:
                eng_tag = "sqlcli"
                db_label = settings.database or "no database"

            try:
                line = session.prompt(
                    [
                        ("class:prompt", f"{eng_tag} "),
                        ("class:database", f"{db_label} "),
                        ("", "› "),
                    ],
                    default=pending_default,
                )
                pending_default = ""
            except EOFError:
                break
            except KeyboardInterrupt:
                pending_default = ""
                print("^C")
                continue

            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith(":"):
                command, _, argument = stripped[1:].partition(" ")
                command = command.lower()
                try:
                    if command in {"quit", "exit", "q"}:
                        break
                    elif command in {"help", "h"}:
                        print_help()
                    elif command in {"autopilot", "auto"}:
                        sql_to_edit = run_autopilot(argument.strip(), database, settings, session)
                        if sql_to_edit:
                            pending_default = sql_to_edit
                    elif command in {"learn", "tutor", "topic", "doc", "w3"}:
                        topic_arg = argument.strip()
                        if not topic_arg:
                            print("\n=== SQL Knowledge Base (W3Schools Syllabus) ===")
                            topics = list_topics()
                            print("Type :learn <topic> for full syntax, explanation, & executable examples:")
                            for index in range(0, len(topics), 4):
                                chunk = topics[index:index + 4]
                                print("  " + "  ".join(f"{t:<18}" for t in chunk))
                            print("\nPopular: :learn create-table  ·  :learn joins  ·  :learn aggregate-functions  ·  :learn constraints\n")
                        else:
                            topic = lookup_topic(topic_arg)
                            if not topic:
                                print(f"Topic '{topic_arg}' not found. Type :learn to see all available topics.")
                            else:
                                print(format_topic_card(topic))
                    elif command in {"gui", "desktop", "app"}:
                        try:
                            from .gui import start_gui_app
                            start_gui_app(engine_manager, settings, database)
                        except Exception as gui_err:
                            print(f"Failed to launch Desktop Studio: {gui_err}")
                    elif command in {"studio", "tui", "dashboard", "dash"}:
                        try:
                            from .tui import start_terminal_studio
                            start_terminal_studio(engine_manager, settings, database)
                        except Exception as tui_err:
                            print(f"Failed to launch Terminal Studio: {tui_err}")
                    elif command in {"web", "browser"}:
                        port_arg = int(argument.strip()) if argument.strip().isdigit() else 8080
                        try:
                            _, p = start_studio_server(engine_manager, port=port_arg, open_browser=True)
                            print_text(HTML(f"\n<ansigreen>✓ Web Studio running at</ansigreen> <b>http://localhost:{p}</b>\n"))
                        except Exception as web_err:
                            print(f"Failed to start web server: {web_err}")
                    elif command in {"engine", "mode"}:
                        target_engine = argument.strip().lower()
                        if not target_engine:
                            print(f"Current active engine: {engine_manager.active_engine.upper()}")
                            print("Available engines: mysql (XAMPP), sqlite (local zero-config), nosql (JSON document store)")
                            print("Usage: :engine mysql | :engine sqlite | :engine nosql")
                        elif target_engine in {"mysql", "sqlite", "nosql"}:
                            engine_manager.active_engine = target_engine
                            print(f"Switched engine to {target_engine.upper()}.")
                            if target_engine == "sqlite":
                                print(f"Using SQLite database: {engine_manager.sqlite.db_path}")
                            elif target_engine == "nosql":
                                print(f"Using NoSQL document store: {engine_manager.nosql.db_path}")
                                print("Tip: Run 'show collections;' or db.<collection>.find(), insert(), delete()")
                        else:
                            print(f"Unknown engine '{target_engine}'. Choose 'mysql', 'sqlite', or 'nosql'.")
                    elif command == "sqlite":
                        db_file = argument.strip()
                        if db_file:
                            engine_manager.sqlite.close()
                            engine_manager.sqlite = SQLiteEngine(db_file)
                        engine_manager.active_engine = "sqlite"
                        print(f"Switched to SQLITE engine: {engine_manager.sqlite.db_path}")
                    elif command == "nosql":
                        db_file = argument.strip()
                        if db_file:
                            engine_manager.nosql.close()
                            engine_manager.nosql = NoSQLEngine(db_file)
                        engine_manager.active_engine = "nosql"
                        print(f"Switched to NOSQL engine: {engine_manager.nosql.db_path}")
                        print("Tip: Run 'show collections;' or db.<collection>.find(), insert(), delete()")
                    elif command == "paste":
                        clipboard_content = get_clipboard_text().strip()
                        if not clipboard_content:
                            print("System clipboard is empty.")
                        elif argument.strip().lower() == "run":
                            print(f"Pasting and running:\n{clipboard_content}")
                            if not clipboard_content.endswith(";"):
                                clipboard_content += ";"
                            res = execute_statement(clipboard_content, database, settings, session, ai_enabled, engine_manager)
                            if res:
                                last_headers, last_rows, _ = res
                                last_sql = clipboard_content
                        else:
                            print(f"Pasting from clipboard:\n{clipboard_content}\n")
                            if not clipboard_content.endswith(";"):
                                clipboard_content += ";"
                            res = execute_statement(clipboard_content, database, settings, session, ai_enabled, engine_manager)
                            if res:
                                last_headers, last_rows, _ = res
                                last_sql = clipboard_content
                    elif command == "copy":
                        target_text = argument.strip() or last_sql
                        if not target_text:
                            print("Nothing to copy. Provide text or run a query first: :copy SELECT * FROM users;")
                        else:
                            if set_clipboard_text(target_text):
                                print(f"Copied to clipboard ({len(target_text)} characters).")
                            else:
                                print("Failed to copy to clipboard.")
                    elif command == "connect":
                        database.connect(argument.strip() or None)
                        print_text(HTML(f"<ansigreen>Connected</ansigreen>  {settings.host}:{settings.port}" + (f" / {settings.database}" if settings.database else "")))
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
                            output.parent.mkdir(parents=True, exist_ok=True)
                            with output.open("w", newline="", encoding="utf-8-sig") as file:
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
                            pass
                        print(
                            f"Loaded {len(database.tables)} tables and "
                            f"{len(database.database_names)} database name(s) for autocomplete."
                        )
                    elif command == "history":
                        print_history(session.history, argument.strip())
                    elif command == "find":
                        find_schema(database, argument)
                    elif command == "save":
                        raw_arg = argument.strip()
                        parts = raw_arg.split(maxsplit=1)
                        if not raw_arg:
                            print("Usage:")
                            print("  :save <name> [SQL]           Save a named SQL snippet (defaults to last query)")
                            print("  :save file <file.sql> [SQL]  Save query to an SQL file on disk")
                            print("  :save output <file.csv|json|txt>")
                            print("                               Save last query result set to disk")
                        elif parts[0].lower() == "file":
                            sub_parts = parts[1].split(maxsplit=1) if len(parts) > 1 else []
                            if not sub_parts:
                                print("Usage: :save file <filepath.sql> [optional SQL statement]")
                            else:
                                file_path = sub_parts[0]
                                sql_to_save = sub_parts[1] if len(sub_parts) > 1 else last_sql
                                save_sql_to_file(file_path, sql_to_save)
                        elif parts[0].lower() == "output":
                            sub_parts = parts[1].split(maxsplit=1) if len(parts) > 1 else []
                            if not sub_parts:
                                print("Usage: :save output <filepath.csv|json|txt>")
                            else:
                                save_output_to_file(sub_parts[0], last_headers, last_rows)
                        elif len(parts) == 1:
                            target_sql = last_sql
                            if not target_sql:
                                print(f"No recent query to save as '{parts[0]}'. Provide SQL: :save {parts[0]} <SQL>")
                            else:
                                save_query(parts[0], target_sql)
                                print(f"Saved query '{parts[0]}': {target_sql}")
                        else:
                            save_query(parts[0], parts[1])
                            print(f"Saved query '{parts[0]}'.")
                    elif command == "saved":
                        queries = load_queries()
                        print("\n".join(f"{name}: {sql}" for name, sql in queries.items()) or "No saved queries.")
                    elif command == "run":
                        name = argument.strip()
                        if not name:
                            print("Usage: :run <name>")
                        else:
                            stmt = get_query(name)
                            res = execute_statement(stmt, database, settings, session, ai_enabled, engine_manager)
                            if res:
                                last_headers, last_rows, _ = res
                                last_sql = stmt
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
                            print_text(HTML(
                                f"\n<ansicyan><b>SQL suggestion</b></ansicyan>  "
                                f"<ansigray>{settings.database or 'no database selected'}</ansigray>"
                            ))
                            print(proposal)
                            print("Review it, then copy and paste it to run. Changes require confirmation.\n")
                    elif command == "chat":
                        action, _, detail = argument.strip().partition(" ")
                        action = action.lower()
                        if action == "reset" and not detail:
                            chat_history.clear()
                            print("Chat history cleared for this run. Saved memory is still available.")
                        elif action == "remember":
                            if not detail.strip():
                                print("Usage: :chat remember <detail>")
                            else:
                                memories = add_memory(detail)
                                print(f"Saved memory #{len(memories)} for future chat sessions.")
                        elif action == "memory" and not detail:
                            memories = load_memories()
                            if memories:
                                print("Saved chat memory:")
                                for index, memory in enumerate(memories, 1):
                                    print(f"{index}. {memory}")
                            else:
                                print("No saved chat memory.")
                        elif action == "forget":
                            if not detail.strip():
                                print("Usage: :chat forget <number|all>")
                            else:
                                memories = remove_memory(detail.strip())
                                print("All saved chat memory was removed." if detail.strip().lower() == "all" else "Saved memory removed.")
                                if memories:
                                    print(f"{len(memories)} saved note(s) remain.")
                        elif action == "reset":
                            print("Usage: :chat reset")
                        elif not argument.strip():
                            print("Usage: :chat <message> | remember <detail> | memory | forget <number|all> | reset")
                        elif not ai_enabled:
                            print("Enable local assistance first with :ai on.")
                        else:
                            ensure_ready(settings)
                            user_message = argument.strip()
                            answer = chat_response(
                                user_message,
                                chat_history,
                                load_memories(),
                                settings.ollama_url,
                                settings.ollama_model,
                            )
                            print(answer + "\n")
                            chat_history.extend([
                                {"role": "user", "content": user_message},
                                {"role": "assistant", "content": answer},
                            ])
                            del chat_history[:-8]
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
                print("That looks like a natural language question. Use :autopilot to build queries, or :chat for conversation:")
                print(f"  :autopilot {stripped}")
                print(f"  :chat {stripped}\n")
                continue

            statement_to_run = stripped if stripped.endswith(";") else stripped + ";"
            res = execute_statement(statement_to_run, database, settings, session, ai_enabled, engine_manager)
            if res:
                last_headers, last_rows, _ = res
                last_sql = statement_to_run
    finally:
        engine_manager.close()
        database.close()
        print("Goodbye.")


if __name__ == "__main__":
    main()
