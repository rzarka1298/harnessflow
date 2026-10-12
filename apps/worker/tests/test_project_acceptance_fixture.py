"""Deterministic multi-task project-run acceptance fixture.

This crosses the real Git worktree, command runner, and durable state boundary while
replacing only the external coding/review model with a deterministic agent.
"""

from __future__ import annotations

import copy
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


class MemoryStore:
    def __init__(self, repo: Path) -> None:
        self.row: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "repository_path": str(repo),
            "name": "Inventory report",
            "prd": "Parse inventory rows and produce a sorted quantity/value report.",
            "status": "queued",
            "reason": "",
            "state": {},
            "control": "",
            "clarification": "",
            "max_attempts": 20,
            "max_duration_seconds": 3600,
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


def check(code: str) -> list[str]:
    return [sys.executable, "-c", "import sys; sys.dont_write_bytecode = True; " + code]


PLAN = {
    "summary": "Parse inventory rows and produce a sorted summary report.",
    "assumptions": ["Rows use name, quantity, and unit price separated by commas."],
    "clarification": "",
    "requirements": [
        {"id": "R1", "description": "Parse inventory rows into typed records."},
        {"id": "R2", "description": "Calculate total quantity and inventory value."},
        {"id": "R3", "description": "Render a stable alphabetically sorted report."},
    ],
    "tasks": [
        {
            "id": "T1",
            "title": "Parse inventory rows",
            "instructions": "Implement parse_rows(rows).",
            "requirement_ids": ["R1"],
            "depends_on": [],
        },
        {
            "id": "T2",
            "title": "Summarize inventory",
            "instructions": "Implement summarize(rows).",
            "requirement_ids": ["R2"],
            "depends_on": ["T1"],
        },
        {
            "id": "T3",
            "title": "Render inventory report",
            "instructions": "Implement render_report(rows).",
            "requirement_ids": ["R3"],
            "depends_on": ["T2"],
        },
    ],
    "checks": [
        {
            "id": "C1",
            "description": "Parse fields and convert quantity and unit price to numbers.",
            "requirement_ids": ["R1"],
            "timeout_seconds": 30,
            "argv": check(
                "from catalog import parse_rows; "
                "assert parse_rows(['pear,2,1.50']) == "
                "[{'name': 'pear', 'quantity': 2, 'unit_price': 1.5}]"
            ),
        },
        {
            "id": "C2",
            "description": "Calculate total quantity and value from parsed rows.",
            "requirement_ids": ["R2"],
            "timeout_seconds": 30,
            "argv": check(
                "from catalog import parse_rows, summarize; "
                "assert summarize(parse_rows(['pear,2,1.50', 'apple,3,2'])) == "
                "{'quantity': 5, 'value': 9.0}"
            ),
        },
        {
            "id": "C3",
            "description": "Render alphabetized names and a stable value total.",
            "requirement_ids": ["R3"],
            "timeout_seconds": 30,
            "argv": check(
                "from catalog import parse_rows, render_report; "
                "assert render_report(parse_rows(['pear,2,1.50', 'apple,3,2'])) == "
                "'apple: 3 @ 2.00\\npear: 2 @ 1.50\\nTotal value: 9.00'"
            ),
        },
    ],
}


INITIAL_MODULE = """def parse_rows(rows):
    parsed = []
    for row in rows:
        name, quantity, unit_price = row.split(",")
        parsed.append({"name": name, "quantity": quantity, "unit_price": float(unit_price)})
    return parsed

"""

COMPLETE_MODULE = """def parse_rows(rows):
    parsed = []
    for row in rows:
        name, quantity, unit_price = row.split(",")
        parsed.append({"name": name, "quantity": int(quantity), "unit_price": float(unit_price)})
    return parsed


def summarize(rows):
    return {
        "quantity": sum(row["quantity"] for row in rows),
        "value": sum(row["quantity"] * row["unit_price"] for row in rows),
    }


def render_report(rows):
    lines = [
        f"{row['name']}: {row['quantity']} @ {row['unit_price']:.2f}"
        for row in sorted(rows, key=lambda row: row["name"])
    ]
    lines.append(f"Total value: {summarize(rows)['value']:.2f}")
    return "\\n".join(lines)
"""


class InventoryAgent(CodexAgent):
    def __init__(self, workspace, model="") -> None:
        super().__init__(workspace, model)
        self.calls: list[str] = []
        self.check_results: list[dict[str, Any]] = []

    async def run(self, prompt, contract, name, poll, timeout, writable=False):
        await poll()
        self.calls.append(contract.__name__)
        if contract is Plan:
            return PLAN, {"input": 1, "output": 1}
        if contract is AgentResult:
            task_id = (
                self._task_id_from_prompt(prompt)
                if "Implement this task and run relevant checks." in prompt
                else "repair"
            )
            if task_id == "T1":
                (self.workspace.path / "catalog.py").write_text(INITIAL_MODULE)
                summary = "Added inventory row parser; quantity conversion needs correction."
            elif task_id == "T2":
                target = self.workspace.path / "catalog.py"
                target.write_text(
                    target.read_text()
                    + """\ndef summarize(rows):
    return {
        "quantity": sum(row["quantity"] for row in rows),
        "value": sum(row["quantity"] * row["unit_price"] for row in rows),
    }
"""
                )
                summary = "Added quantity and value aggregation."
            elif task_id == "T3":
                (self.workspace.path / "catalog.py").write_text(
                    COMPLETE_MODULE.replace('"quantity": int(quantity)', '"quantity": quantity')
                )
                summary = "Added sorted report rendering."
            else:
                (self.workspace.path / "catalog.py").write_text(COMPLETE_MODULE)
                summary = "Repaired quantity parsing after acceptance checks exposed string values."
            return {"summary": summary, "blocked_reason": ""}, {"input": 1, "output": 1}
        if contract is JudgeVerdict:
            return self._judge_result(contract), {"input": 1, "output": 1}
        return {"passed": True, "findings": []}, {"input": 1, "output": 1}

    @staticmethod
    def _task_id_from_prompt(prompt: str) -> str:
        for task_id in ("T1", "T2", "T3"):
            if f'"id":"{task_id}"' in prompt or f'"id": "{task_id}"' in prompt:
                return task_id
        # Repair prompts contain no task payload; engine phase is encoded in context.
        return "repair"

    @staticmethod
    def _judge_result(contract) -> dict[str, Any]:
        fields = contract.model_fields
        verdicts = [
            {
                "requirement_id": key,
                "passed": True,
                "reason": "Behavior is implemented and checked.",
            }
            for key in ("R1", "R2", "R3")
        ]
        values: dict[str, Any] = {
            "passed": True,
            "findings": [],
            "requirement_verdicts": verdicts,
        }
        return {key: values[key] for key in fields if key in values}

    async def verify_command(self, argv, name, poll, timeout):
        result = await run_process(argv, self.workspace.path, timeout, poll)
        self.check_results.append({"argv": argv, "exit_code": result.exit_code})
        return result


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    target = tmp_path / "inventory-repo"
    target.mkdir()
    subprocess.run(["git", "init", "-q", str(target)], check=True)
    return target


@pytest.mark.asyncio
async def test_multi_task_prd_repairs_failed_check_and_judges_delivered_commit(
    repo: Path, tmp_path: Path
) -> None:
    store = MemoryStore(repo)
    agents: list[InventoryAgent] = []

    def factory(workspace, model):
        agent = InventoryAgent(workspace, model)
        agents.append(agent)
        return agent

    result = {"status": "queued", "reason": ""}
    for _ in range(30):
        result = await tick(store, tmp_path / "data", agent_factory=factory)
        if result["status"] in {"completed", "blocked", "failed", "exhausted"}:
            break

    assert result["status"] == "completed", result
    state = store.row["state"]
    assert state["completed_task_ids"] == ["T1", "T2", "T3"]
    assert state["attempts"] == 4  # three planned tasks and one check-driven repair
    check_runs = [call for agent in agents for call in agent.check_results]
    assert [call["exit_code"] == 0 for call in check_runs] == [
        False,
        False,
        False,
        True,
        True,
        True,
    ]
    assert all(item["passed"] for item in state["evidence"])
    assert all(item["commit"] == state["head_commit"] for item in state["evidence"])
    assert state["review"] == {"passed": True, "findings": []}
    assert state["judge"]["passed"] is True
    assert {v["requirement_id"] for v in state["judge"]["requirement_verdicts"]} == {
        "R1",
        "R2",
        "R3",
    }
    assert state["judge"]["commit"] == state["head_commit"]
    assert sum(JudgeVerdict.__name__ in agent.calls for agent in agents) == 1
    assert state["phase"] == "deliver"
    assert not (repo / "catalog.py").exists()
    worktree = Path(state["workspace_path"])
    result_check = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.dont_write_bytecode = True; "
            "from catalog import parse_rows, render_report; "
            "print(render_report(parse_rows(['pear,2,1.50', 'apple,3,2'])))",
        ],
        cwd=worktree,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result_check.stdout.splitlines() == [
        "apple: 3 @ 2.00",
        "pear: 2 @ 1.50",
        "Total value: 9.00",
    ]
    assert (
        subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"], cwd=repo, capture_output=True
        ).returncode
        != 0
    )
