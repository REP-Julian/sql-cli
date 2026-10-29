# SQLCLI plugins

Put Python files in this folder. Each module must define `register(registry)`.
SQLCLI imports and runs these files at startup, so only add plugin code you trust.

```python
def register(registry):
    registry.command("hello", lambda argument, database: print("Hello from a plugin!"))
    registry.completer(lambda text: ["CUSTOM_FUNCTION"] if "CUSTOM" in text.upper() else [])
```

Installed Python packages can also expose the `sqlcli.plugins` entry-point group.
