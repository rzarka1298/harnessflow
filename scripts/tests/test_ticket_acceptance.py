"""The ticket fixture starts from a dirty existing checkout and rejects missing triage."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "ticket-acceptance.py"


class TicketAcceptanceTests(unittest.TestCase):
    def test_prepare_preserves_a_dirty_existing_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "prepare", "--root", directory],
                check=True,
                capture_output=True,
                text=True,
            )
            prepared = json.loads(result.stdout)
            repo = Path(prepared["repository"])
            self.assertTrue((repo / "workqueue" / "cli.py").is_file())
            self.assertTrue((repo / "tests" / "test_cli.py").is_file())
            self.assertFalse(any(repo.rglob("__pycache__")))
            self.assertEqual(
                (repo / "private-token.txt").read_text(), "LOCAL_TOKEN=never-copy-me\n"
            )
            self.assertTrue((repo / "README.md").read_text().endswith("Local draft note.\n"))
            status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo, text=True)
            self.assertEqual(status.splitlines(), [" M README.md", "?? private-token.txt"])

    def test_verify_rejects_unextended_starter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prepared = json.loads(
                subprocess.check_output(
                    [sys.executable, str(SCRIPT), "prepare", "--root", directory], text=True
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
            self.assertIn("triage", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
