"""Resource checks that keep local model work conservative on Windows laptops."""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

MAX_CPU_PERCENT = 80.0
MAX_MEMORY_PERCENT = 80.0
MIN_AVAILABLE_GB = 4.0


def estimated_model_ram_gb(model: str) -> float:
    """Conservative working-memory allowance, including Ollama overhead."""
    normalized = model.lower()
    if normalized.startswith("qwen3.5:0.8b"):
        return 2.0
    if normalized.startswith("qwen3.5:2b"):
        return 3.6
    if normalized.startswith("qwen3.5:4b"):
        return 4.5
    if normalized.startswith("qwen3.5:9b"):
        return 10.0
    if normalized.startswith("qwen3.5:27b"):
        return 22.0
    if normalized.startswith("qwen3.5:35b"):
        return 28.0
    if normalized.startswith("qwen3.5:122b"):
        return 90.0
    if normalized.startswith("qwen3:0.6b"):
        return 2.0
    if normalized.startswith("qwen3:1.7b"):
        return 3.0
    if normalized.startswith("qwen3:4b"):
        return 4.5
    if normalized.startswith("qwen3:8b"):
        return 7.0
    return 5.0


class _FileTime(ctypes.Structure):
    _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

    def value(self) -> int:
        return (self.high << 32) | self.low


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.DWORD),
        ("memory_load", wintypes.DWORD),
        ("total_phys", ctypes.c_ulonglong),
        ("avail_phys", ctypes.c_ulonglong),
        ("total_page_file", ctypes.c_ulonglong),
        ("avail_page_file", ctypes.c_ulonglong),
        ("total_virtual", ctypes.c_ulonglong),
        ("avail_virtual", ctypes.c_ulonglong),
        ("avail_extended_virtual", ctypes.c_ulonglong),
    ]


def _system_times() -> tuple[int, int]:
    idle, kernel, user = _FileTime(), _FileTime(), _FileTime()
    if not ctypes.windll.kernel32.GetSystemTimes(
        ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
    ):
        raise OSError("Windows could not read CPU usage.")
    return idle.value(), kernel.value() + user.value()


def measure_resources(sample_seconds: float = 0.4) -> tuple[float, float]:
    """Return current total CPU percentage and available physical RAM in GB."""
    if os.name != "nt":
        raise RuntimeError("SQLCLI's local AI resource guard currently supports Windows measurements only.")
    before_idle, before_total = _system_times()
    time.sleep(sample_seconds)
    after_idle, after_total = _system_times()
    total_delta = max(1, after_total - before_total)
    idle_delta = max(0, after_idle - before_idle)
    cpu_percent = max(0.0, min(100.0, 100.0 * (total_delta - idle_delta) / total_delta))

    memory = _MemoryStatusEx()
    memory.length = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise OSError("Windows could not read available memory.")
    available_gb = memory.avail_phys / (1024 ** 3)
    return cpu_percent, available_gb


def total_physical_memory_gb() -> float:
    """Return installed physical RAM in GB."""
    if os.name != "nt":
        raise RuntimeError("SQLCLI's local AI resource guard currently supports Windows measurements only.")
    memory = _MemoryStatusEx()
    memory.length = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise OSError("Windows could not read total physical memory.")
    return memory.total_phys / (1024 ** 3)


def require_ai_resources(model_ram_gb: float = 0.0) -> tuple[float, float]:
    """Pause local model work when CPU or projected RAM use reaches 80%."""
    try:
        cpu_percent, available_gb = measure_resources()
        total_gb = total_physical_memory_gb()
    except (OSError, RuntimeError) as exc:
        raise RuntimeError(f"AI paused because SQLCLI could not safely check CPU and memory: {exc}") from exc
    return check_ai_resources(
        cpu_percent,
        available_gb,
        total_memory_gb=total_gb,
        model_ram_gb=model_ram_gb,
    )


def check_ai_resources(
    cpu_percent: float,
    available_gb: float,
    min_available_gb: float = MIN_AVAILABLE_GB,
    *,
    total_memory_gb: float | None = None,
    model_ram_gb: float = 0.0,
) -> tuple[float, float]:
    """Validate a measured snapshot, including the model's projected RAM use."""
    projected_memory_percent = None
    if total_memory_gb and total_memory_gb > 0:
        projected_used_gb = total_memory_gb - available_gb + max(0.0, model_ram_gb)
        projected_memory_percent = 100.0 * projected_used_gb / total_memory_gb
    memory_is_high = (
        projected_memory_percent >= MAX_MEMORY_PERCENT
        if projected_memory_percent is not None
        else available_gb < min_available_gb
    )
    if cpu_percent >= MAX_CPU_PERCENT or memory_is_high:
        ram_detail = (
            f"projected RAM use {projected_memory_percent:.0f}% after loading the model"
            if projected_memory_percent is not None
            else f"free RAM {available_gb:.1f} GB"
        )
        raise RuntimeError(
            f"AI paused to protect your laptop (CPU {cpu_percent:.0f}%, {ram_detail}). "
            f"Close other apps and try again when CPU and projected RAM use are below "
            f"{MAX_CPU_PERCENT:.0f}%. SQLCLI is still open."
        )
    return cpu_percent, available_gb
