import tempfile
import unittest
from pathlib import Path

from workqueue.store import load, save


class StoreTests(unittest.TestCase):
    def test_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(load(Path(directory) / "missing.json"), [])

    def test_round_trip_preserves_legacy_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.json"
            rows = [{"id": 7, "title": "Legacy", "status": "open", "priority": "low"}]
            save(path, rows)
            self.assertEqual(load(path), rows)


if __name__ == "__main__":
    unittest.main()
