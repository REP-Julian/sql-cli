"""Resource checks that keep local model work conservative on Windows laptops."""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

MAX_CPU_PERCENT = 60.0
MIN_AVAILABLE_GB = 4.0


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


def require_ai_resources() -> tuple[float, float]:
    """Pause local model work when CPU is busy or free RAM is low."""
    try:
        cpu_percent, available_gb = measure_resources()
    except (OSError, RuntimeError) as exc:
        raise RuntimeError(f"AI paused because SQLCLI could not safely check CPU and memory: {exc}") from exc
    return check_ai_resources(cpu_percent, available_gb)


def check_ai_resources(cpu_percent: float, available_gb: float) -> tuple[float, float]:
    """Validate a previously measured CPU/RAM snapshot."""
    if cpu_percent >= MAX_CPU_PERCENT or available_gb < MIN_AVAILABLE_GB:
        raise RuntimeError(
            f"AI paused to protect your laptop (CPU {cpu_percent:.0f}%, free RAM {available_gb:.1f} GB). "
            f"Close other apps and try again when CPU is below {MAX_CPU_PERCENT:.0f}% and at least "
            f"{MIN_AVAILABLE_GB:.0f} GB RAM is free. SQLCLI is still open."
        )
    return cpu_percent, available_gb
