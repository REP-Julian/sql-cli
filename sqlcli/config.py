"""Configuration loading for SQLCLI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str | None = None
    ai_enabled: bool = False
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:4b"


def load_settings() -> Settings:
    load_dotenv(Path.cwd() / ".env")
    return Settings(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE") or None,
        ai_enabled=os.getenv("SQLCLI_AI_ENABLED", "false").lower() in {"1", "true", "yes", "on"},
        ollama_url=os.getenv("SQLCLI_OLLAMA_URL", "http://localhost:11434").rstrip("/"),
        ollama_model=os.getenv("SQLCLI_OLLAMA_MODEL", "qwen3.5:4b"),
    )
