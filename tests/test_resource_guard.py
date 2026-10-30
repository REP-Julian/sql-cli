import unittest

from sqlcli.resource_guard import check_ai_resources


class ResourceGuardTests(unittest.TestCase):
    def test_allows_ai_when_resources_are_within_budget(self):
        self.assertEqual(check_ai_resources(35, 8.0), (35, 8.0))

    def test_pauses_ai_when_cpu_is_too_high(self):
        with self.assertRaisesRegex(RuntimeError, "CPU 80%"):
            check_ai_resources(80, 8.0)

    def test_pauses_ai_when_free_ram_is_too_low(self):
        with self.assertRaisesRegex(RuntimeError, "free RAM 3.9 GB"):
            check_ai_resources(25, 3.9)


if __name__ == "__main__":
    unittest.main()
