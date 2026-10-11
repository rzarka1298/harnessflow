import unittest

from workqueue.service import add, close, listed


class ServiceTests(unittest.TestCase):
    def test_add_and_close(self):
        records = []
        ticket = add(records, "Patch server", "high", "2026-06-01", ["ops"])
        self.assertEqual(ticket["id"], 1)
        self.assertEqual(ticket["status"], "open")
        self.assertEqual(close(records, 1)["status"], "closed")
        self.assertEqual(listed(records, "open"), [])

    def test_ids_continue_after_existing_records(self):
        records = [{"id": 4, "status": "open", "title": "Old", "priority": "low"}]
        self.assertEqual(add(records, "New", "medium", None, [])["id"], 5)


if __name__ == "__main__":
    unittest.main()
