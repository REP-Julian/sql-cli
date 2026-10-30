"""Start and inspect the local Ollama service from SQLCLI on Windows."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from .config import Settings
from .resource_guard import estimated_model_ram_gb, require_ai_resources


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ollama_paths() -> tuple[str | None, Path]:
    root = _project_root()
    binary = os.getenv("SQLCLI_OLLAMA_BIN") or str(root / "ollama" / "ollama.exe")
    if not Path(binary).is_file():
        binary = shutil.which("ollama")
    models = Path(os.getenv("SQLCLI_OLLAMA_MODELS") or os.getenv("OLLAMA_MODELS") or (root / "models"))
    return binary, models


def _service_info(url: str) -> tuple[str | None, set[str]]:
    try:
        with urlopen(f"{url}/api/tags", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        names = {model.get("name", "") for model in payload.get("models", [])}
        return "running", names
    except (URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None, set()


def status(settings: Settings) -> str:
    state, models = _service_info(settings.ollama_url)
    if not state:
        return f"Ollama is stopped or unreachable at {settings.ollama_url}. Type :ollama start."
    if settings.ollama_model in models:
        return f"Ollama is running and connected to {settings.ollama_model}."
    available = ", ".join(sorted(models)) if models else "none"
    return (
        f"Ollama is running, but {settings.ollama_model} is not installed in its active model folder. "
        f"Available models: {available}. Type :ollama pull to download the configured model."
    )


def start(settings: Settings) -> str:
    current, models = _service_info(settings.ollama_url)
    if current:
        return status(settings)

    cpu_percent, available_gb = require_ai_resources()
    print(f"Resource check passed: CPU {cpu_percent:.0f}%, {available_gb:.1f} GB RAM available.")

    binary, models_path = _ollama_paths()
    if not binary:
        raise RuntimeError("Could not find Ollama. Install it in C:\\sqlCLI\\ollama or set SQLCLI_OLLAMA_BIN.")
    models_path.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["OLLAMA_MODELS"] = str(models_path)
    env["OLLAMA_MAX_LOADED_MODELS"] = "1"
    env["OLLAMA_NUM_PARALLEL"] = "1"
    creation_flags = 0
    startupinfo = None
    if os.name == "nt":
        # :ask may start Ollama automatically. Keep that background service
        # out of the user's terminal by suppressing its console window.
        creation_flags = subprocess.CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
    subprocess.Popen(
        [binary, "serve"],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creation_flags,
        startupinfo=startupinfo,
    )

    for _ in range(30):
        time.sleep(0.5)
        current, models = _service_info(settings.ollama_url)
        if current:
            if settings.ollama_model in models:
                return f"Ollama started and connected to {settings.ollama_model}."
            available = ", ".join(sorted(models)) if models else "none"
            return (
                f"Ollama started, but {settings.ollama_model} is not installed. "
                f"Available models: {available}. Type :ollama pull to download it."
            )
    raise RuntimeError(f"Ollama did not start. Check that port 11434 is available and try again.")


def ensure_ready(settings: Settings) -> None:
    # Check before starting a service or allowing a model request.
    cpu_percent, available_gb = require_ai_resources(estimated_model_ram_gb(settings.ollama_model))
    print(f"AI safety check passed: CPU {cpu_percent:.0f}%, {available_gb:.1f} GB RAM available; projected use is below 80%.")
    start(settings)
    current, models = _service_info(settings.ollama_url)
    if not current:
        raise RuntimeError("Ollama stopped before SQLCLI could connect. Type :ollama start and try again.")
    if settings.ollama_model not in models:
        raise RuntimeError(
            f"Model {settings.ollama_model} is not installed. Type :ollama pull to download and connect it."
        )


def pull(settings: Settings) -> str:
    cpu_percent, available_gb = require_ai_resources()
    print(f"Resource check passed: CPU {cpu_percent:.0f}%, {available_gb:.1f} GB RAM available.")
    state, _ = _service_info(settings.ollama_url)
    if not state:
        start(settings)
    binary, models_path = _ollama_paths()
    if not binary:
        raise RuntimeError("Could not find Ollama. Install it in C:\\sqlCLI\\ollama first.")
    env = os.environ.copy()
    env["OLLAMA_MODELS"] = str(models_path)
    result = subprocess.run(
        [binary, "pull", settings.ollama_model],
        env=env,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Ollama could not download {settings.ollama_model} (exit code {result.returncode}).")
    return status(settings)


def reset_model(settings: Settings) -> str:
    """Unload the configured model without stopping SQLCLI or Ollama."""
    running, _ = _service_info(settings.ollama_url)
    if not running:
        return "No Ollama session is active. Each :ask request already starts with fresh context."
    binary, _ = _ollama_paths()
    if not binary:
        raise RuntimeError("Could not find the Ollama command. Check the install folder under C:\\sqlCLI.")
    result = subprocess.run(
        [binary, "stop", settings.ollama_model],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        if any(phrase in detail.lower() for phrase in ("not running", "not loaded", "no running model")):
            return f"{settings.ollama_model} is already unloaded. Your next :ask starts with a fresh context."
        raise RuntimeError(detail or f"Could not unload {settings.ollama_model}.")
    return f"Reset complete. {settings.ollama_model} was unloaded; your next :ask starts fresh."
