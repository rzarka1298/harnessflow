"""The expense acceptance fixture is repeatable and preserves its source checkout."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "expense-acceptance.py"


class ExpenseAcceptanceTests(unittest.TestCase):
    def test_prepare_creates_existing_repo_with_private_note(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "prepare", "--root", directory],
                capture_output=True,
                text=True,
                check=True,
            )
            prepared = json.loads(result.stdout)
            repo = Path(prepared["repository"])
            self.assertTrue((repo / "expenses.py").is_file())
            self.assertTrue((repo / "tests" / "test_expenses.py").is_file())
            self.assertEqual((repo / "private-notes.txt").read_text(), "Keep this note private.\n")
            status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo, text=True)
            self.assertEqual(status.strip(), "?? private-notes.txt")
            self.assertEqual(
                prepared["base_commit"],
                subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
            )

    def test_verify_rejects_starter_without_report_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prepared = json.loads(
                subprocess.check_output(
                    [sys.executable, str(SCRIPT), "prepare", "--root", directory],
                    text=True,
                )
            )
            workspace = Path(directory) / "worktree"
            subprocess.run(
                [
                    "git",
                    "-C",
                    prepared["repository"],
                    "worktree",
                    "add",
                    "--detach",
                    str(workspace),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "verify",
                    "--root",
                    directory,
                    "--workspace",
                    str(workspace),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("report", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
