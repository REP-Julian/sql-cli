# SQLCLI plugins

Put Python files in this folder. Each module must define `register(registry)`.
SQLCLI imports and runs these files at startup, so only add plugin code you trust.

Registered command names are suggested when the user types `:` and presses Tab.
Completion callbacks run while the user types SQL or a command argument. They
receive the full text before the cursor and return candidate strings; SQLCLI
shows only candidates that match what the user has typed so far.

```python
def register(registry):
    registry.command("hello", lambda argument, database: print("Hello from a plugin!"))

    def suggest(text):
        # Example: offer a SQL function in a SELECT expression.
        if text.upper().endswith("SELECT "):
            return ["CURRENT_USER()"]
        # Example: offer an argument after the :hello command.
        if text.lower().startswith(":hello "):
            return ["world"]
        return []

    registry.completer(suggest)
```

Installed Python packages can also expose the `sqlcli.plugins` entry-point group.
