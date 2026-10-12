"""Public project-run boundary: real Git/commands, deterministic external coding agent."""

from __future__ import annotations

import copy
import fcntl
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest

from harnessflow_worker.projects.agent import CodexAgent
from harnessflow_worker.projects.engine import tick
from harnessflow_worker.projects.models import AgentResult, JudgeVerdict, Plan
from harnessflow_worker.projects.process import run_process
from harnessflow_worker.projects.workspace import repository_lock_name


class MemoryStore:
    """Replace the database boundary while preserving durable copy semantics."""

    def __init__(self, repo: Path) -> None:
        self.row: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "repository_path": str(repo),
            "name": "Greeting",
            "prd": "Create greeting.txt containing hello",
            "status": "queued",
            "reason": "",
            "state": {},
            "control": "",
            "clarification": "",
            "max_attempts": 30,
            "max_duration_seconds": 14400,
            "model": "",
            "request_pr": False,
        }

    async def load(self) -> dict[str, Any]:
        return copy.deepcopy(self.row)

    async def save(self, state: dict[str, Any], status: str, reason: str = "") -> str:
        self.row.update(state=copy.deepcopy(state), status=status, reason=reason)
        return status

    async def consume_control(self, control: str, version: int) -> None:
        if self.row["control"] == control:
            self.row["control"] = ""


class FixtureAgent(CodexAgent):
    async def run(self, prompt, contract, name, poll, timeout, writable=False):
        await poll()
        if contract is Plan:
            return {
                "summary": "Greeting",
                "assumptions": [],
                "clarification": "",
                "requirements": [{"id": "R1", "description": "hello greeting"}],
                "tasks": [
                    {
                        "id": "T1",
                        "title": "Greeting",
                        "instructions": "write greeting",
                        "requirement_ids": ["R1"],
                        "depends_on": [],
                    }
                ],
                "checks": [
                    {
                        "id": "C1",
                        "description": "assert greeting",
                        "requirement_ids": ["R1"],
                        "timeout_seconds": 30,
                        "argv": [
                            sys.executable,
                            "-c",
                            "from pathlib import Path; "
                            "assert Path('greeting.txt').read_text() == 'hello'",
                        ],
                    }
                ],
            }, {"input": 1, "output": 1}
        if contract is AgentResult:
            target = self.workspace.path / "greeting.txt"
            target.write_text("hello" if target.exists() else "wrong")
            return {"summary": "Created greeting", "blocked_reason": ""}, {"input": 1, "output": 1}
        if contract is JudgeVerdict:
            return {
                "passed": True,
                "findings": [],
                "requirement_verdicts": [
                    {"requirement_id": "R1", "passed": True, "reason": "Greeting behavior verified"}
                ],
            }, {"input": 1, "output": 1}
        return {"passed": True, "findings": []}, {"input": 1, "output": 1}

    async def verify_command(self, argv, name, poll, timeout):
        return await run_process(argv, self.workspace.path, timeout, poll)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    target = tmp_path / "repo"
    target.mkdir()
    subprocess.run(["git", "init", "-q", str(target)], check=True)
    return target


@pytest.mark.asyncio
async def test_new_project_repairs_failed_check_and_delivers_exact_verified_commit(
    repo: Path, tmp_path: Path
) -> None:
    store = MemoryStore(repo)
    for _ in range(18):
        result = await tick(store, tmp_path / "data", agent_factory=FixtureAgent)
        if result["status"] in {"completed", "blocked", "failed"}:
            break
    assert result["status"] == "completed", result
    state = store.row["state"]
    assert state["attempts"] == 2
    assert state["evidence"][0]["passed"] is True
    assert state["evidence"][0]["commit"] == state["head_commit"]
    assert state["judge"]["passed"] is True
    assert state["judge"]["commit"] == state["head_commit"]
    assert not (repo / "greeting.txt").exists()
    assert (
        subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"], cwd=repo, capture_output=True
        ).returncode
        != 0
    )
    assert {a["name"] for a in state["artifacts"]} == {
        "verification.md",
        "changes.diff",
        "acceptance.json",
    }


@pytest.mark.asyncio
async def test_judge_findings_route_through_repair_before_delivery(
    repo: Path, tmp_path: Path
) -> None:
    calls = 0

    class FailingJudgeOnce(FixtureAgent):
        async def run(self, prompt, contract, name, poll, timeout, writable=False):
            nonlocal calls
            if contract is JudgeVerdict:
                calls += 1
                if calls == 1:
                    await poll()
                    return {
                        "passed": False,
                        "findings": ["Greeting needs another acceptance review"],
                        "requirement_verdicts": [
                            {"requirement_id": "R1", "passed": False, "reason": "Review again"}
                        ],
                    }, {"input": 1, "output": 1}
            return await super().run(prompt, contract, name, poll, timeout, writable)

    store = MemoryStore(repo)
    for _ in range(22):
        result = await tick(store, tmp_path / "data", agent_factory=FailingJudgeOnce)
        if result["status"] in {"completed", "blocked", "failed", "exhausted"}:
            break
    assert result["status"] == "completed", result
    assert calls == 2
    assert store.row["state"]["attempts"] == 3
    assert any(
        "judge found acceptance gaps" in item["message"].lower()
        for item in store.row["state"]["events"]
    )


@pytest.mark.asyncio
async def test_dirty_original_checkout_survives_pause_resume_and_cancellation(
    repo: Path, tmp_path: Path
) -> None:
    (repo / "personal.txt").write_text("uncommitted work")
    store = MemoryStore(repo)
    await tick(store, tmp_path / "data", agent_factory=FixtureAgent)
    store.row["control"] = "pause"
    assert (await tick(store, tmp_path / "data", agent_factory=FixtureAgent))["status"] == "paused"
    before = copy.deepcopy(store.row["state"])
    assert (await tick(store, tmp_path / "data", agent_factory=FixtureAgent))["status"] == "paused"
    assert store.row["state"] == before
    store.row["control"] = "resume"
    assert (await tick(store, tmp_path / "data", agent_factory=FixtureAgent))[
        "status"
    ] == "planning"
    store.row["control"] = "cancel"
    assert (await tick(store, tmp_path / "data", agent_factory=FixtureAgent))[
        "status"
    ] == "canceled"
    assert (repo / "personal.txt").read_text() == "uncommitted work"


@pytest.mark.asyncio
async def test_cancellation_waits_for_existing_process_ownership(
    repo: Path, tmp_path: Path
) -> None:
    store = MemoryStore(repo)
    store.row["control"] = "cancel"
    locks = tmp_path / "data" / "locks"
    locks.mkdir(parents=True)
    with (locks / repository_lock_name(str(repo))).open("a") as existing:
        fcntl.flock(existing, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert (await tick(store, tmp_path / "data", agent_factory=FixtureAgent))[
            "status"
        ] == "running"
        assert store.row["status"] == "queued"
        assert store.row["control"] == "cancel"
    assert (await tick(store, tmp_path / "data", agent_factory=FixtureAgent))[
        "status"
    ] == "canceled"


@pytest.mark.asyncio
async def test_attempt_exhaustion_preserves_work_and_resumes_after_explicit_extension(
    repo: Path, tmp_path: Path
) -> None:
    store = MemoryStore(repo)
    store.row["max_attempts"] = 1
    for _ in range(10):
        result = await tick(store, tmp_path / "data", agent_factory=FixtureAgent)
        if result["status"] == "exhausted":
            break
    assert result["status"] == "exhausted"
    assert store.row["state"]["attempts"] == 1
    assert (
        Path(store.row["state"]["workspace_path"]).joinpath("greeting.txt").read_text() == "wrong"
    )
    store.row["max_attempts"] += 1
    store.row["control"] = "resume"
    for _ in range(8):
        result = await tick(store, tmp_path / "data", agent_factory=FixtureAgent)
        if result["status"] == "completed":
            break
    assert result["status"] == "completed", result


@pytest.mark.asyncio
async def test_subprocess_deadline_is_enforced(tmp_path: Path) -> None:
    result = await run_process([sys.executable, "-c", "import time; time.sleep(60)"], tmp_path, 0.2)
    assert result.exit_code == 124


@pytest.mark.asyncio
async def test_resume_persists_running_before_consuming_command(repo: Path, tmp_path: Path) -> None:
    class CrashAfterConsume(MemoryStore):
        async def consume_control(self, control: str, version: int) -> None:
            assert self.row["status"] == "running"
            await super().consume_control(control, version)
            raise RuntimeError("simulated worker death after acknowledging resume")

    store = CrashAfterConsume(repo)
    store.row.update(status="blocked", control="resume")
    store.row["state"] = {"failure_count": 3, "repeated_failures": 3}
    with pytest.raises(RuntimeError, match="simulated worker death"):
        await tick(store, tmp_path / "data", agent_factory=FixtureAgent)
    assert store.row["status"] == "running"
    assert store.row["control"] == ""
    assert store.row["state"]["repeated_failures"] == 0
    # A new activity can now progress without a second resume signal.
    assert (await tick(store, tmp_path / "data", agent_factory=FixtureAgent))["status"] == "running"


@pytest.mark.asyncio
async def test_interrupted_attempt_is_recovered_without_marking_task_complete(
    repo: Path, tmp_path: Path
) -> None:
    store = MemoryStore(repo)
    for _ in range(3):
        await tick(store, tmp_path / "data", agent_factory=FixtureAgent)
    state = store.row["state"]
    assert state["phase"] == "implement"
    Path(state["workspace_path"]).joinpath("greeting.txt").write_text("partial")
    state["agent_attempts"].append({"id": "crashed", "status": "running"})
    store.row["max_attempts"] = 0
    result = await tick(store, tmp_path / "data", agent_factory=FixtureAgent)
    assert result["status"] == "exhausted"
    assert store.row["state"]["completed_task_ids"] == []
    assert store.row["state"]["agent_attempts"][-1]["status"] == "interrupted"
    git_status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=state["workspace_path"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert git_status.stdout == ""


@pytest.mark.asyncio
async def test_tick_reports_store_resolved_final_status(repo: Path, tmp_path: Path) -> None:
    class CancelAtDelivery(MemoryStore):
        async def save(self, state, status, reason=""):
            # Mirrors the DB fence when cancel arrives after the final process poll.
            if status == "completed":
                status = "canceled"
            return await super().save(state, status, reason)

    store = CancelAtDelivery(repo)
    for _ in range(18):
        result = await tick(store, tmp_path / "data", agent_factory=FixtureAgent)
        if result["status"] == "canceled":
            break
    assert result["status"] == "canceled"
