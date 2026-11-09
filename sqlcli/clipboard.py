"""Cross-platform clipboard helpers with native Windows ctypes support."""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from typing import Any

from prompt_toolkit.clipboard import Clipboard, ClipboardData

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


def _get_windows_clipboard() -> str:
    """Read unicode text from Windows clipboard via ctypes without third-party deps."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_wchar_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        pointer = kernel32.GlobalLock(handle)
        text = str(pointer) if pointer else ""
        kernel32.GlobalUnlock(handle)
        return text
    except Exception:
        return ""
    finally:
        user32.CloseClipboard()


def _set_windows_clipboard(text: str) -> bool:
    """Write unicode text to Windows clipboard via ctypes."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE

    encoded = (text + "\0").encode("utf-16-le")
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
    if not handle:
        return False

    pointer = kernel32.GlobalLock(handle)
    if not pointer:
        kernel32.GlobalFree(handle)
        return False

    ctypes.memmove(pointer, encoded, len(encoded))
    kernel32.GlobalUnlock(handle)

    if not user32.OpenClipboard(None):
        kernel32.GlobalFree(handle)
        return False
    try:
        user32.EmptyClipboard()
        return bool(user32.SetClipboardData(CF_UNICODETEXT, handle))
    finally:
        user32.CloseClipboard()


def get_clipboard_text() -> str:
    """Return text currently on the system clipboard."""
    if os.name == "nt":
        text = _get_windows_clipboard()
        if text:
            return text
    # Fallback via tkinter if available
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            return root.clipboard_get() or ""
        finally:
            root.destroy()
    except Exception:
        pass
    return ""


def set_clipboard_text(text: str) -> bool:
    """Set text on the system clipboard."""
    if os.name == "nt":
        if _set_windows_clipboard(text):
            return True
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
            return True
        finally:
            root.destroy()
    except Exception:
        pass
    return False


class SystemClipboard(Clipboard):
    """Prompt-toolkit Clipboard backed by the operating system clipboard."""

    def __init__(self) -> None:
        self._in_memory: str = ""

    def set_data(self, data: ClipboardData) -> None:
        self._in_memory = data.text
        set_clipboard_text(data.text)

    def get_data(self) -> ClipboardData:
        system_text = get_clipboard_text()
        return ClipboardData(system_text or self._in_memory)
