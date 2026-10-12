"""Publication cannot infer an unrelated GitHub repository or base branch."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from harnessflow_worker.projects import engine
from harnessflow_worker.projects.process import Result

BASE = "a" * 40
HEAD = "b" * 40


class PublicationWorkspace:
    def __init__(
        self,
        root: Path,
        push_url: str = "git@github.com:owner/repo.git",
        diff_content: str = "verified diff",
    ) -> None:
        self.path = self.root = root
        self.branch = "harnessflow/run-id"
        self.lock_fd = 10
        self.push_url = push_url
        self.diff_content = diff_content

    async def git(self, *args: str) -> str:
        return {
            ("remote", "get-url", "origin"): "https://github.com/owner/repo.git",
            ("remote", "get-url", "--push", "origin"): self.push_url,
            ("rev-parse", "HEAD"): HEAD,
            ("status", "--porcelain"): "",
        }[args]

    async def diff(self, base: str) -> str:
        assert base == BASE
        return self.diff_content


def snapshot() -> dict[str, Any]:
    return {
        "base_commit": BASE,
        "completed_task_ids": ["T1"],
        "review": {"passed": True, "findings": []},
        "plan": {
            "summary": "Feature",
            "assumptions": [],
            "clarification": "",
            "requirements": [{"id": "R1", "description": "Feature"}],
            "tasks": [
                {
                    "id": "T1",
                    "title": "Build",
                    "instructions": "Build it",
                    "requirement_ids": ["R1"],
                    "depends_on": [],
                }
            ],
            "checks": [
                {
                    "id": "C1",
                    "description": "Test",
                    "requirement_ids": ["R1"],
                    "argv": ["python3", "test.py"],
                    "timeout_seconds": 30,
                }
            ],
        },
        "evidence": [
            {
                "check_id": "C1",
                "requirement_ids": ["R1"],
                "argv": ["python3", "test.py"],
                "passed": True,
                "exit_code": 0,
                "commit": HEAD,
            }
        ],
    }


@pytest.mark.asyncio
async def test_delivery_keeps_full_diff_artifact(tmp_path: Path) -> None:
    diff = "a" * 500_000 + "final line\n"
    state = snapshot()
    result = await engine._deliver(
        {"name": "Feature", "request_pr": False},
        state,
        PublicationWorkspace(tmp_path, diff_content=diff),
        AsyncMock(),
        lambda: 120,
    )
    assert result == ("completed", "")
    artifact = next(item for item in state["artifacts"] if item["name"] == "changes.diff")
    assert artifact["content"] == diff


@pytest.mark.asyncio
async def test_publication_pins_origin_repository_default_base_and_verified_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = AsyncMock(
        side_effect=[
            Result(0, f"ref: refs/heads/main\tHEAD\n{BASE}\tHEAD\n", ""),
            Result(0, "", ""),
            Result(0, "[]", ""),
            Result(0, "https://github.com/owner/repo/pull/1\n", ""),
        ]
    )
    monkeypatch.setattr(engine, "run_process", runner)
    state = snapshot()
    result = await engine._deliver(
        {"name": "Feature", "request_pr": True},
        state,
        PublicationWorkspace(tmp_path),
        AsyncMock(),
        lambda: 120,
    )
    assert result == ("completed", "")
    calls = [call.args[0] for call in runner.call_args_list]
    assert calls[1] == [
        "git",
        "-c",
        "core.hooksPath=/dev/null",
        "push",
        "git@github.com:owner/repo.git",
        f"{HEAD}:refs/heads/harnessflow/run-id",
    ]
    for argv in calls[2:]:
        assert argv[argv.index("--repo") + 1] == "owner/repo"
        assert argv[argv.index("--base") + 1] == "main"
    assert state["publication_target"]["base_commit"] == BASE


@pytest.mark.asyncio
async def test_nondefault_or_stale_base_prevents_any_push(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = AsyncMock(
        return_value=Result(0, f"ref: refs/heads/main\tHEAD\n{'c' * 40}\tHEAD\n", "")
    )
    monkeypatch.setattr(engine, "run_process", runner)
    with pytest.raises(ValueError, match="saved base commit"):
        await engine._deliver(
            {"name": "Feature", "request_pr": True},
            snapshot(),
            PublicationWorkspace(tmp_path),
            AsyncMock(),
            lambda: 120,
        )
    assert runner.call_count == 1
    assert runner.call_args.args[0][1] == "ls-remote"


@pytest.mark.asyncio
async def test_mismatched_push_destination_fails_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = AsyncMock()
    monkeypatch.setattr(engine, "run_process", runner)
    with pytest.raises(ValueError, match="fetch and push repositories differ"):
        await engine._publication_target(
            PublicationWorkspace(tmp_path, "git@github.com:other/repo.git"),
            snapshot(),
            AsyncMock(),
            lambda: 120,
        )
    runner.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/repo",
        "https://github.com.evil.test/a/b",
        "https://token@github.com/a/b",
        "ssh://git@other.test/a/b",
    ],
)
def test_unsupported_origins_fail_closed(url: str) -> None:
    with pytest.raises(ValueError, match=r"GitHub\.com origin"):
        engine._github_repository(url)
