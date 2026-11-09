"""User-controlled local memory for SQLCLI's chat assistant."""

from __future__ import annotations

import json
from pathlib import Path

MAX_MEMORIES = 20
MAX_MEMORY_LENGTH = 300


def _path() -> Path:
    return Path.home() / ".sqlcli_memory.json"


def load_memories() -> list[str]:
    """Read saved memories from the user's profile."""
    path = _path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read chat memory: {exc}") from exc
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        raise RuntimeError("Chat memory file has an invalid format.")
    if len(data) > MAX_MEMORIES or any(not item.strip() or len(item) > MAX_MEMORY_LENGTH for item in data):
        raise RuntimeError("Chat memory file exceeds the supported limits.")
    return data


def _save(memories: list[str]) -> None:
    path = _path()
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_text(json.dumps(memories, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
    except OSError as exc:
        raise RuntimeError(f"Could not save chat memory: {exc}") from exc


def add_memory(note: str) -> list[str]:
    """Save one user-provided note and return the updated list."""
    note = note.strip()
    if not note:
        raise RuntimeError("Memory text cannot be empty.")
    if len(note) > MAX_MEMORY_LENGTH:
        raise RuntimeError(f"Keep each memory to {MAX_MEMORY_LENGTH} characters or fewer.")
    memories = load_memories()
    if any(item.casefold() == note.casefold() for item in memories):
        raise RuntimeError("That memory is already saved.")
    if len(memories) >= MAX_MEMORIES:
        raise RuntimeError(f"Chat memory is full ({MAX_MEMORIES} notes). Remove a note before adding another.")
    memories.append(note)
    _save(memories)
    return memories


def remove_memory(selection: str) -> list[str]:
    """Remove a one-based memory number or clear all memories."""
    memories = load_memories()
    if selection.strip().lower() == "all":
        _save([])
        return []
    try:
        index = int(selection) - 1
    except ValueError as exc:
        raise RuntimeError("Use :chat forget <number|all>.") from exc
    if not 0 <= index < len(memories):
        raise RuntimeError(f"Memory number must be from 1 to {len(memories)}.")
    memories.pop(index)
    _save(memories)
    return memories
