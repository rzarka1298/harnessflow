#!/usr/bin/env python3
"""Opt-in real Codex acceptance: new and existing local Git projects, no publication."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

GREETING = 'def greet(name):\n    return "Hello, " + name + "!"\n'
NOTE = "Keep this uncommitted note.\n"
WAITING = {"paused", "blocked", "exhausted"}


def fixture_baseline(repo: Path, kind: str) -> dict:
    """Recover old smoke baselines from the known fixture, never its current changes."""
    files = (
        {}
        if kind == "new"
        else {
            "greeting.py": GREETING,
            ".gitignore": "__pycache__/\n",
            "personal-notes.txt": NOTE,
        }
    )
    expected_status = "" if kind == "new" else "?? personal-notes.txt"
    assert git(repo, "status", "--porcelain") == expected_status, "original fixture status changed"
    assert sorted(p.name for p in repo.iterdir() if p.name != ".git") == sorted(files), (
        "original fixture files changed"
    )
    for name, content in files.items():
        assert (repo / name).read_text() == content, f"original {name} changed"
    if kind == "new":
        try:
            git(repo, "rev-parse", "--verify", "HEAD")
        except subprocess.CalledProcessError:
            head = None
        else:
            raise AssertionError("original new fixture must retain its unborn HEAD")
    else:
        assert git(repo, "rev-list", "--count", "HEAD") == "1", "original HEAD advanced"
        assert git(repo, "show", "-s", "--format=%s", "HEAD") == "Initial greeting"
        assert git(repo, "show", "HEAD:greeting.py") == GREETING.strip()
        assert git(repo, "show", "HEAD:.gitignore") == "__pycache__/"
        assert git(repo, "ls-tree", "--name-only", "HEAD").splitlines() == [
            ".gitignore",
            "greeting.py",
        ]
        head = git(repo, "rev-parse", "HEAD")
    return {
        "kind": kind,
        "head": head,
        "ref": git(repo, "symbolic-ref", "HEAD"),
        "status": expected_status,
        "files": files,
    }


def rpc(base: str, method: str, body: dict) -> dict:
    request = urllib.request.Request(
        f"{base}/harnessflow.project.v1.ProjectService/{method}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Connect-Protocol-Version": "1"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        [
            "git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "user.name=HarnessFlow Smoke",
            "-c",
            "user.email=smoke@localhost",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            *args,
        ],
        cwd=repo,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8080")
    parser.add_argument("--kind", choices=["new", "existing"])
    parser.add_argument("--resume-run", help="Resume or verify an earlier smoke run UUID")
    parser.add_argument("--clarification", default="", help="Clarification sent when resuming")
    parser.add_argument("--model", default="")
    args = parser.parse_args()
    if not args.resume_run and not args.kind:
        parser.error("--kind is required for a new smoke run")
    if args.clarification and not args.resume_run:
        parser.error("--clarification requires --resume-run")
    baseline_snapshot = None
    awaiting_resume = False
    if args.resume_run:
        run = rpc(args.api, "GetRun", {"id": args.resume_run})["run"]
        project = rpc(args.api, "GetProject", {"id": run["projectId"]})["project"]
        kinds = {f"Real Codex {kind} smoke": kind for kind in ["new", "existing"]}
        if project.get("name") not in kinds:
            parser.error("--resume-run must refer to a project created by this smoke script")
        kind = kinds[project["name"]]
        if args.kind and args.kind != kind:
            parser.error("--kind conflicts with the original smoke fixture")
        args.kind = kind
        repo = Path(project["repositoryPath"])
        root = repo.parent
        original = fixture_baseline(repo, kind)
        metadata = root / "smoke-metadata.json"
        if metadata.exists():
            saved = json.loads(metadata.read_text())
            assert saved["baseline"] == original, "original repository changed since creation"
            assert saved["run_id"] == run["id"], "smoke metadata belongs to a different run"
        if run["status"] in WAITING:
            baseline_snapshot = json.loads(run.get("snapshotJson", "{}"))
            rpc(
                args.api,
                "ControlRun",
                {
                    "runId": run["id"],
                    "action": "resume",
                    "clarification": args.clarification,
                },
            )
            awaiting_resume = True
        elif run["status"] in {"failed", "canceled"}:
            parser.error(f"run is terminal ({run['status']}); create a new smoke instead")
    else:
        root = Path(tempfile.mkdtemp(prefix=f"harnessflow-{args.kind}-"))
        repo = root / "repository"
        repo.mkdir()
        git(repo, "init", "-q")
    if not args.resume_run and args.kind == "existing":
        (repo / "greeting.py").write_text(GREETING)
        (repo / ".gitignore").write_text("__pycache__/\n")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "Initial greeting")
        (repo / "personal-notes.txt").write_text(NOTE)
        prd = (
            "Extend greeting.py greet(name) to strip surrounding whitespace from a name, "
            "use World for empty or whitespace-only names, and preserve Hello, Ada! for Ada. "
            "Add Python standard-library unittest coverage for ordinary, empty and padded names. "
            "No external dependencies, UI, deployment or publication. Keep this a tiny change. "
            "Acceptance must execute behavioral assertions, not just inspect files."
        )
    elif not args.resume_run:
        prd = (
            "Create a tiny Python standard-library project. greeting.py exports greet(name), "
            "returning Hello, <name>! after trimming whitespace; empty names use World. "
            "Running python3 greeting.py Ada prints Hello, Ada!; with no arguments prints "
            "Hello, World!. Add unittest tests for names, whitespace, empty names "
            "and CLI behavior. "
            "Add a short README with run/test commands and .gitignore for Python caches. "
            "No third-party dependencies, UI, deployment or publication. One implementation task "
            "is sufficient. Acceptance must execute behavioral assertions."
        )
    if not args.resume_run:
        original = fixture_baseline(repo, args.kind)
        project = rpc(
            args.api,
            "CreateProject",
            {
                "name": f"Real Codex {args.kind} smoke",
                "repositoryPath": str(repo),
                "prd": prd,
            },
        )["project"]
        run = rpc(
            args.api,
            "StartRun",
            {
                "projectId": project["id"],
                "maxAttempts": 6,
                "maxDurationSeconds": 1200,
                "model": args.model,
                "requestPr": False,
            },
        )["run"]
    (root / "smoke-metadata.json").write_text(
        json.dumps(
            {"baseline": original, "project_id": project["id"], "run_id": run["id"]},
            indent=2,
        )
    )
    print(
        json.dumps({"repository": str(repo), "project_id": project["id"], "run_id": run["id"]}),
        flush=True,
    )
    deadline = time.monotonic() + 1300
    acknowledgment_deadline = time.monotonic() + 60
    last = None
    while time.monotonic() < deadline:
        run = rpc(args.api, "GetRun", {"id": run["id"]})["run"]
        state = json.loads(run.get("snapshotJson", "{}"))
        if awaiting_resume:
            # ControlRun returns the old status until the worker consumes the command.
            # A fresh checkpoint also acknowledges an immediate re-block after resume.
            if run["status"] not in WAITING or state != baseline_snapshot:
                awaiting_resume = False
            elif time.monotonic() >= acknowledgment_deadline:
                raise TimeoutError(f"Resume was not acknowledged within 60s for {run['id']}")
        progress = (run["status"], state.get("phase"), state.get("attempts"))
        if progress != last:
            print(
                json.dumps({"progress": progress, "reason": run.get("reason", "")}),
                flush=True,
            )
            last = progress
        if not awaiting_resume and run["status"] in {
            "completed",
            "failed",
            "canceled",
            *WAITING,
        }:
            (root / "result.json").write_text(json.dumps(run, indent=2))
            if run["status"] != "completed":
                raise RuntimeError(f"Smoke run {run['status']}: {run.get('reason')}; {root}")
            assert fixture_baseline(repo, args.kind) == original
            workspace = Path(state["workspace_path"])
            subprocess.run(
                ["python3", "-m", "unittest", "discover", "-v"],
                cwd=workspace,
                check=True,
            )
            subprocess.run(
                [
                    "python3",
                    "-c",
                    "from greeting import greet; assert greet(' Ada ') == 'Hello, Ada!'; "
                    "assert greet('  ') == 'Hello, World!'",
                ],
                cwd=workspace,
                check=True,
            )
            print(
                f"PASS: {args.kind}; branch={state['branch']}; evidence={root / 'result.json'}",
                flush=True,
            )
            return
        time.sleep(2)
    rpc(args.api, "ControlRun", {"runId": run["id"], "action": "cancel"})
    raise TimeoutError(f"Smoke run timed out; cancellation requested for {run['id']}")


if __name__ == "__main__":
    main()
