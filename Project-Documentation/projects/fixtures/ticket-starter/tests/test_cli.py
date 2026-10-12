import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliTests(unittest.TestCase):
    def test_add_list_and_close(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "tickets.json")
            base = [sys.executable, "-m", "workqueue", "--file", path]
            added = subprocess.run(
                [*base, "add", "Patch server", "--priority", "high", "--tag", "ops"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(added.stdout.strip(), "Added #1")
            listing = subprocess.run([*base, "list"], capture_output=True, text=True, check=True)
            self.assertEqual(listing.stdout.strip(), "#1 [open] high - Patch server (ops)")
            closed = subprocess.run(
                [*base, "close", "1"], capture_output=True, text=True, check=True
            )
            self.assertEqual(closed.stdout.strip(), "Closed #1")

    def test_import_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "tickets.json")
            csv = Path("examples/incoming.csv")
            result = subprocess.run(
                [sys.executable, "-m", "workqueue", "--file", path, "import-csv", str(csv)],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(result.stdout.strip(), "Imported 2 tickets")


if __name__ == "__main__":
    unittest.main()
