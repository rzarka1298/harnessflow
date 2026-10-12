"""Prepare and externally verify the larger existing-ticket-project fixture."""

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
STARTER = ROOT / "Project-Documentation/projects/fixtures/ticket-starter"
PRD = ROOT / "Project-Documentation/projects/fixtures/ticket-triage-prd.md"
PRIVATE_NOTE = "LOCAL_TOKEN=never-copy-me\n"
LOCAL_DRAFT = "\nLocal draft note.\n"


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.excludesFile=/dev/null",
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
    ).rstrip("\n")


def prepare(root: Path) -> dict[str, str]:
    root = root.resolve()
    repo = root / "repository"
    if repo.exists() or (root / "fixture.json").exists():
        raise ValueError(f"fixture already exists at {root}")
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(STARTER, repo, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Initial WorkQueue application")
    base_commit = git(repo, "rev-parse", "HEAD")
    (repo / "private-token.txt").write_text(PRIVATE_NOTE, encoding="utf-8")
    with (repo / "README.md").open("a", encoding="utf-8") as handle:
        handle.write(LOCAL_DRAFT)
    metadata = {"repository": str(repo), "base_commit": base_commit, "prd": str(PRD)}
    (root / "fixture.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def run_cli(workspace: Path, file: Path, *args: str, success: bool = True) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "workqueue", "--file", str(file), *args],
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if success and result.returncode:
        raise ValueError(f"workqueue {' '.join(args)} failed: {result.stderr.strip()}")
    if not success and (result.returncode == 0 or not result.stderr.strip()):
        raise ValueError(f"workqueue {' '.join(args)} did not reject invalid input readably")
    return (result.stdout if success else result.stderr).strip()


def verify(root: Path, workspace: Path) -> dict[str, str | int]:
    root = root.resolve(strict=True)
    metadata = json.loads((root / "fixture.json").read_text(encoding="utf-8"))
    repo = Path(metadata["repository"]).resolve(strict=True)
    workspace = workspace.resolve(strict=True)
    if repo == workspace:
        raise ValueError("verification requires the delivered worktree, not the original checkout")
    if git(repo, "rev-parse", "HEAD") != metadata["base_commit"]:
        raise ValueError("original repository HEAD changed")
    if git(repo, "status", "--porcelain") != " M README.md\n?? private-token.txt":
        raise ValueError("original repository working tree changed")
    if (repo / "private-token.txt").read_text(encoding="utf-8") != PRIVATE_NOTE:
        raise ValueError("original private token changed")
    for source in STARTER.rglob("*"):
        if source.is_file() and "__pycache__" not in source.parts and source.suffix != ".pyc":
            relative = source.relative_to(STARTER)
            expected = source.read_bytes() + (
                LOCAL_DRAFT.encode() if relative == Path("README.md") else b""
            )
            if (repo / relative).read_bytes() != expected:
                raise ValueError(f"original starter file changed: {relative}")
    if (workspace / "private-token.txt").exists() or b"never-copy-me" in (
        workspace / "README.md"
    ).read_bytes():
        raise ValueError("private source data leaked into the delivered worktree")
    if (workspace / "README.md").read_text(encoding="utf-8").endswith("Local draft note.\n"):
        raise ValueError("uncommitted source README was copied into the delivered worktree")

    with tempfile.TemporaryDirectory(prefix="harnessflow-ticket-verify-") as directory:
        file = Path(directory) / "tickets.json"
        commands = (
            ("Legacy", "low", "2026-05-29", []),
            ("Patch server", "high", "2026-05-30", ["ops", "security"]),
            ("Rotate key", "high", "2026-05-30", ["security"]),
            ("Audit logs", "medium", "2026-06-01", ["ops"]),
            ("Later", "high", "2026-06-02", ["ops"]),
            ("No deadline", "low", None, ["ops"]),
            ("Backup server", "high", "2026-05-30", ["ops"]),
        )
        for title, priority, due, tags in commands:
            args = ["add", title, "--priority", priority]
            if due:
                args.extend(["--due", due])
            for tag in tags:
                args.extend(["--tag", tag])
            run_cli(workspace, file, *args)
        if run_cli(workspace, file, "close", "3") != "Closed #3":
            raise ValueError("existing close command regressed")
        listed = run_cli(workspace, file, "list", "--status", "closed")
        if listed != "#3 [closed] high 2026-05-30 Rotate key (security)":
            raise ValueError(f"existing list command regressed: {listed!r}")
        records = json.loads(file.read_text(encoding="utf-8"))
        records[5].pop("due")
        records[5].pop("tags")
        file.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        before = file.read_bytes()
        report = run_cli(workspace, file, "triage", "--as-of", "2026-06-01")
        expected = (
            "#2 [high] 2026-05-30 Patch server (ops,security)\n"
            "#7 [high] 2026-05-30 Backup server (ops)\n"
            "#4 [medium] 2026-06-01 Audit logs (ops)\n"
            "#1 [low] 2026-05-29 Legacy (-)\n"
            "Total: 4"
        )
        if report != expected:
            raise ValueError(f"triage priority, due or text output is wrong: {report!r}")
        tagged = run_cli(workspace, file, "triage", "--as-of", "2026-06-01", "--tag", "ops")
        if tagged != (
            "#2 [high] 2026-05-30 Patch server (ops,security)\n"
            "#7 [high] 2026-05-30 Backup server (ops)\n"
            "#4 [medium] 2026-06-01 Audit logs (ops)\nTotal: 3"
        ):
            raise ValueError(f"triage exact tag filtering is wrong: {tagged!r}")
        if run_cli(workspace, file, "triage", "--as-of", "2026-06-01", "--tag", "op") != "Total: 0":
            raise ValueError("triage tag filtering used substring matching")
        if run_cli(workspace, file, "triage", "--as-of", "2026-05-28") != "Total: 0":
            raise ValueError("triage empty selection is wrong")
        json_report = json.loads(
            run_cli(workspace, file, "triage", "--as-of", "2026-06-01", "--format", "json")
        )
        if json_report != {
            "as_of": "2026-06-01",
            "count": 4,
            "tickets": [
                {
                    "id": 2,
                    "title": "Patch server",
                    "priority": "high",
                    "due": "2026-05-30",
                    "tags": ["ops", "security"],
                },
                {
                    "id": 7,
                    "title": "Backup server",
                    "priority": "high",
                    "due": "2026-05-30",
                    "tags": ["ops"],
                },
                {
                    "id": 4,
                    "title": "Audit logs",
                    "priority": "medium",
                    "due": "2026-06-01",
                    "tags": ["ops"],
                },
                {"id": 1, "title": "Legacy", "priority": "low", "due": "2026-05-29", "tags": []},
            ],
        }:
            raise ValueError(f"triage JSON output is wrong: {json_report!r}")
        if run_cli(workspace, file, "triage", "--as-of", "2026-06-01") != report:
            raise ValueError("triage output is not deterministic")
        for invalid_date in ("2026-02-30", "2026-6-1", "20260601", "2026-06-01T00:00:00"):
            error = run_cli(workspace, file, "triage", "--as-of", invalid_date, success=False)
            if "date" not in error.lower() and "as-of" not in error.lower():
                raise ValueError(f"invalid date error is unclear: {error!r}")
        if file.read_bytes() != before:
            raise ValueError("triage mutated the ticket file")
        missing = Path(directory) / "missing.json"
        if run_cli(workspace, missing, "triage", "--as-of", "2026-06-01") != "Total: 0":
            raise ValueError("triage on a missing file is wrong")
        if missing.exists():
            raise ValueError("triage created a missing ticket file")
        csv = workspace / "examples" / "incoming.csv"
        if run_cli(workspace, file, "import-csv", str(csv)) != "Imported 2 tickets":
            raise ValueError("existing CSV import regressed")

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
    if not count or int(count.group(1)) < 10:
        raise ValueError("delivered project lacks triage test coverage")
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
    create = commands.add_parser("prepare", help="create a dirty existing repository")
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
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        parser.exit(2, f"ticket-acceptance: {exc}\n")


if __name__ == "__main__":
    main()
