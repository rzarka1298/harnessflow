"""Project completion is an evidence decision, not an agent's final message."""

import pytest
from pydantic import ValidationError

from harnessflow_worker.projects.models import Plan, completion_ready


def plan_data() -> dict:
    return {
        "summary": "Add a greeting command",
        "assumptions": [],
        "requirements": [{"id": "R1", "description": "Greets the named user"}],
        "tasks": [
            {
                "id": "T1",
                "title": "Greeting",
                "instructions": "Implement greeting",
                "requirement_ids": ["R1"],
                "depends_on": [],
            }
        ],
        "checks": [
            {
                "id": "C1",
                "description": "Greeting behavior",
                "requirement_ids": ["R1"],
                "argv": ["python3", "-m", "unittest"],
                "timeout_seconds": 60,
            }
        ],
        "clarification": "",
    }


def test_completion_requires_current_passing_evidence_for_every_requirement() -> None:
    plan = Plan.model_validate(plan_data())
    evidence = [
        {
            "check_id": "C1",
            "requirement_ids": ["R1"],
            "passed": True,
            "exit_code": 0,
            "commit": "abc",
            "argv": ["python3", "-m", "unittest"],
        }
    ]
    judge = {
        "passed": True,
        "findings": [],
        "requirement_verdicts": [
            {"requirement_id": "R1", "passed": True, "reason": "Observed behavior"}
        ],
        "commit": "abc",
    }
    assert completion_ready(plan, ["T1"], evidence, "abc", True, judge)
    assert not completion_ready(plan, ["T1"], evidence, "abc", True)
    assert not completion_ready(plan, ["T1"], [], "abc", True, judge)
    assert not completion_ready(plan, ["T1"], evidence, "new-commit", True, judge)
    assert not completion_ready(plan, [], evidence, "abc", True, judge)
    assert not completion_ready(plan, ["T1"], evidence, "abc", False, judge)
    assert not completion_ready(plan, ["T1"], evidence, "abc", True, {**judge, "commit": "old"})
    assert not completion_ready(
        plan, ["T1"], evidence, "abc", True, {**judge, "requirement_verdicts": []}
    )
    evidence[0]["exit_code"] = 1
    assert not completion_ready(plan, ["T1"], evidence, "abc", True, judge)


def test_plan_rejects_uncovered_requirements_and_cyclic_tasks() -> None:
    data = plan_data()
    data["checks"] = []
    with pytest.raises(ValidationError):
        Plan.model_validate(data)
    data = plan_data()
    data["tasks"][0]["depends_on"] = ["T1"]
    with pytest.raises(ValidationError):
        Plan.model_validate(data)
