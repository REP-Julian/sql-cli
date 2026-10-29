"""Small plugin registry with local modules and Python entry-point support."""

from __future__ import annotations

import importlib.metadata
import importlib.util
from pathlib import Path
from typing import Callable


class PluginRegistry:
    def __init__(self):
        self.commands: dict[str, Callable] = {}
        self._completers: list[Callable[[str], list[str]]] = []
        self.names: list[str] = []

    def command(self, name: str, handler: Callable) -> None:
        self.commands[name] = handler

    def completer(self, callback: Callable[[str], list[str]]) -> None:
        self._completers.append(callback)

    def completions(self, text: str) -> list[str]:
        result = []
        for callback in self._completers:
            try:
                result.extend(callback(text))
            except Exception as exc:
                print(f"Plugin completion error: {exc}")
        return result


def load_plugins(registry: PluginRegistry) -> None:
    plugin_dir = Path.cwd() / "plugins"
    plugin_dir.mkdir(exist_ok=True)
    for path in sorted(plugin_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"sqlcli_local_{path.stem}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.register(registry)
            registry.names.append(path.stem)
        except Exception as exc:
            print(f"Could not load plugin {path.name}: {exc}")
    try:
        entries = importlib.metadata.entry_points(group="sqlcli.plugins")
        for entry in entries:
            entry.load()(registry)
            registry.names.append(entry.name)
    except Exception as exc:
        print(f"Could not load installed plugins: {exc}")
