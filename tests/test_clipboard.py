import unittest
from prompt_toolkit.clipboard import ClipboardData
from sqlcli.clipboard import SystemClipboard, get_clipboard_text, set_clipboard_text


class ClipboardTests(unittest.TestCase):
    def test_get_clipboard_text_returns_str(self):
        text = get_clipboard_text()
        self.assertIsInstance(text, str)

    def test_system_clipboard_in_memory_fallback(self):
        clipboard = SystemClipboard()
        clipboard.set_data(ClipboardData("SELECT 42;"))
        self.assertEqual(clipboard.get_data().text, "SELECT 42;")


if __name__ == "__main__":
    unittest.main()
