"""Prepare and verify an existing-repository project-run acceptance fixture."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "Project-Documentation/projects/fixtures/expense-starter"
PRD = ROOT / "Project-Documentation/projects/fixtures/expense-report-prd.md"
PRIVATE_NOTE = "Keep this note private.\n"


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "core.fsmonitor=false",
            "-c",
            "user.name=HarnessFlow Acceptance",
            "-c",
            "user.email=acceptance@localhost",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            *args,
        ],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def prepare(root: Path) -> dict[str, str]:
    root = root.resolve()
    repo = root / "repository"
    if repo.exists() or (root / "fixture.json").exists():
        raise ValueError(f"fixture already exists at {root}")
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(STARTER, repo)
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Initial expense ledger")
    base_commit = git(repo, "rev-parse", "HEAD")
    (repo / "private-notes.txt").write_text(PRIVATE_NOTE, encoding="utf-8")
    metadata = {"repository": str(repo), "base_commit": base_commit, "prd": str(PRD)}
    (root / "fixture.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def run_cli(
    workspace: Path, *args: str, expect_success: bool = True
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "expenses.py", *args],
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if expect_success and result.returncode:
        raise ValueError(f"expense CLI {' '.join(args)} failed: {result.stderr.strip()}")
    if not expect_success and (result.returncode == 0 or not result.stderr.strip()):
        raise ValueError(f"expense CLI {' '.join(args)} did not reject invalid input readably")
    return result


def verify(root: Path, workspace: Path) -> dict[str, str | int]:
    root = root.resolve(strict=True)
    metadata = json.loads((root / "fixture.json").read_text(encoding="utf-8"))
    repo = Path(metadata["repository"]).resolve(strict=True)
    workspace = workspace.resolve(strict=True)
    if workspace == repo:
        raise ValueError("verification requires the delivered worktree, not the original checkout")
    if git(repo, "rev-parse", "HEAD") != metadata["base_commit"]:
        raise ValueError("original repository HEAD changed")
    if git(repo, "status", "--porcelain") != "?? private-notes.txt":
        raise ValueError("original repository working tree changed")
    if (repo / "private-notes.txt").read_text(encoding="utf-8") != PRIVATE_NOTE:
        raise ValueError("original private note changed")
    for source in STARTER.rglob("*"):
        if source.is_file():
            relative = source.relative_to(STARTER)
            if (repo / relative).read_bytes() != source.read_bytes():
                raise ValueError(f"original starter file changed: {relative}")

    with tempfile.TemporaryDirectory(prefix="harnessflow-expense-verify-") as directory:
        ledger = Path(directory) / "ledger.json"
        for spent_on, category, amount in (
            ("2026-01-02", "Food", "0.10"),
            ("2026-01-03", "Food", "0.20"),
            ("2026-02-01", "Travel", "5.00"),
            ("2026-02-02", "food", "1.00"),
        ):
            run_cli(workspace, "--file", str(ledger), "add", spent_on, category, amount)
        listed = run_cli(workspace, "--file", str(ledger), "list").stdout.strip()
        if listed != (
            "2026-01-02 | Food | 0.10\n"
            "2026-01-03 | Food | 0.20\n"
            "2026-02-01 | Travel | 5.00\n"
            "2026-02-02 | food | 1.00"
        ):
            raise ValueError(f"existing list behavior regressed: {listed!r}")
        before = ledger.read_bytes()
        ranged = run_cli(
            workspace,
            "--file",
            str(ledger),
            "report",
            "--from",
            "2026-01-02",
            "--to",
            "2026-02-01",
        ).stdout.strip()
        if ranged != "Food: 0.30\nTravel: 5.00\nTotal: 5.30":
            raise ValueError(f"report range or decimal behavior is wrong: {ranged!r}")
        single = run_cli(
            workspace, "--file", str(ledger), "report", "--from", "2026-02-02"
        ).stdout.strip()
        if single != "food: 1.00\nTotal: 1.00":
            raise ValueError(f"report lower bound or exact category grouping is wrong: {single!r}")
        empty = run_cli(
            workspace, "--file", str(ledger), "report", "--to", "2025-12-31"
        ).stdout.strip()
        if empty != "Total: 0.00":
            raise ValueError(f"empty report is wrong: {empty!r}")
        for invalid in (
            ("--from", "not-a-date"),
            ("--from", "2026-02-03", "--to", "2026-01-01"),
        ):
            run_cli(
                workspace,
                "--file",
                str(ledger),
                "report",
                *invalid,
                expect_success=False,
            )
        if ledger.read_bytes() != before:
            raise ValueError("report mutated the ledger")

    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if tests.returncode:
        raise ValueError(f"delivered tests failed: {tests.stdout}{tests.stderr}")
    count = re.search(r"Ran (\d+) tests?", tests.stdout + tests.stderr)
    if not count or int(count.group(1)) < 3:
        raise ValueError("delivered project did not add report test coverage")
    commit = git(workspace, "rev-parse", "HEAD")
    if commit == metadata["base_commit"]:
        raise ValueError("delivered worktree contains no committed change")
    if git(workspace, "status", "--porcelain"):
        raise ValueError("delivered worktree has uncommitted files")
    return {
        "status": "passed",
        "workspace": str(workspace),
        "commit": commit,
        "tests": int(count.group(1)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("prepare", help="create a committed starter plus private note")
    create.add_argument("--root", type=Path, required=True)
    check = commands.add_parser("verify", help="check source isolation and delivered behavior")
    check.add_argument("--root", type=Path, required=True)
    check.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            print(json.dumps(prepare(args.root)))
        else:
            print(json.dumps(verify(args.root, args.workspace)))
    except (
        OSError,
        ValueError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ) as exc:
        parser.exit(2, f"expense-acceptance: {exc}\n")


if __name__ == "__main__":
    main()
