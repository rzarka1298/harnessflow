"""Global skill installation is repeatable and never overwrites user content."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "install-agent-skills.py"


class InstallAgentSkillsTests(unittest.TestCase):
    def test_install_is_idempotent_and_refuses_different_existing_skill(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            command = [sys.executable, str(SCRIPT), "--home", home]
            first = subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertIn("Codex: installed", first.stdout)
            self.assertIn("Claude Code: installed", first.stdout)
            second = subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertIn("already installed", second.stdout)
            codex = Path(home) / ".agents/skills/harnessflow-project/SKILL.md"
            codex.write_text("user customization", encoding="utf-8")
            third = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(third.returncode, 0)
            self.assertIn("Nothing was overwritten", third.stderr)
            self.assertEqual(codex.read_text(encoding="utf-8"), "user customization")


if __name__ == "__main__":
    unittest.main()
