"""The plan contract and the single completion predicate."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Requirement(Contract):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)


class Task(Contract):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    requirement_ids: list[str] = Field(min_length=1)
    depends_on: list[str]


class Check(Contract):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    requirement_ids: list[str] = Field(min_length=1)
    argv: list[str] = Field(min_length=1)
    timeout_seconds: int = Field(ge=1, le=1800)

    @model_validator(mode="after")
    def executable(self) -> Check:
        if not self.argv[0].strip() or self.argv[0] in {"true", "echo", "printf", ":"}:
            raise ValueError("acceptance checks must execute substantive assertions")
        return self


class Plan(Contract):
    summary: str
    assumptions: list[str]
    requirements: list[Requirement] = Field(min_length=1)
    tasks: list[Task] = Field(min_length=1)
    checks: list[Check] = Field(min_length=1)
    clarification: str

    @model_validator(mode="after")
    def complete_graph(self) -> Plan:
        for label, ids in [
            ("requirements", [r.id for r in self.requirements]),
            ("tasks", [t.id for t in self.tasks]),
            ("checks", [c.id for c in self.checks]),
        ]:
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {label} IDs")
        requirements = {r.id for r in self.requirements}
        tasks = {t.id for t in self.tasks}
        for refs in [
            *[t.requirement_ids for t in self.tasks],
            *[c.requirement_ids for c in self.checks],
        ]:
            if not set(refs) <= requirements:
                raise ValueError("unknown requirement reference")
        covered = {r for c in self.checks for r in c.requirement_ids}
        assigned = {r for t in self.tasks for r in t.requirement_ids}
        if covered != requirements or assigned != requirements:
            raise ValueError("every requirement needs an implementation task and acceptance check")
        visited: set[str] = set()
        while len(visited) < len(tasks):
            ready = {t.id for t in self.tasks if set(t.depends_on) <= visited} - visited
            if not ready:
                raise ValueError("task dependencies contain a cycle or unknown task")
            visited |= ready
        return self


class AgentResult(Contract):
    summary: str
    blocked_reason: str


class Review(Contract):
    passed: bool = Field(description="True only when there are no blocking defects or gaps.")
    findings: list[str] = Field(
        description="Blocking defects or requirement gaps only. Empty when passed is true. "
        "Never include positive observations, explanations of success, or review summaries."
    )


def completion_ready(
    plan: Plan,
    completed: list[str],
    evidence: list[dict[str, Any]],
    commit: str,
    review_passed: bool,
) -> bool:
    """All required checks must pass against the exact delivered revision."""
    if not commit or not review_passed or set(completed) != {t.id for t in plan.tasks}:
        return False
    by_check = {e.get("check_id"): e for e in evidence}
    return all(
        (e := by_check.get(check.id)) is not None
        and e.get("passed") is True
        and e.get("exit_code") == 0
        and e.get("commit") == commit
        and e.get("argv") == check.argv
        and set(e.get("requirement_ids", [])) == set(check.requirement_ids)
        for check in plan.checks
    )
