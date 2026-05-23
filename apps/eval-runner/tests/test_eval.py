"""Offline unit tests for scorers, dataset loading, and report aggregation.
The live runner (needs api+worker) is exercised separately."""

from __future__ import annotations

import pytest

from harnessflow_eval.dataset import load_cases
from harnessflow_eval.report import aggregate
from harnessflow_eval.scorers import ExactMatch, LLMJudge
from harnessflow_eval.types import Case, CaseResult, RunOutcome


@pytest.mark.asyncio
async def test_exact_match() -> None:
    s = ExactMatch()
    case = Case(id="c", expected="Hello  World")
    assert await s.score(case, RunOutcome(output="hello world")) == 1.0
    assert await s.score(case, RunOutcome(output="goodbye")) == 0.0
    # No reference -> 0.
    assert await s.score(Case(id="c"), RunOutcome(output="x")) == 0.0


@pytest.mark.asyncio
async def test_llm_judge_mock_is_neutral() -> None:
    # With no provider keys, build_default_client uses MockProvider whose canned
    # text has no number, so the judge returns the neutral 0.5.
    s = LLMJudge()
    score = await s.score(
        Case(id="c", criteria="must mention temporal"),
        RunOutcome(output="[mock] something about temporal"),
    )
    assert score == 0.5


@pytest.mark.asyncio
async def test_llm_judge_parses_numeric_verdict() -> None:
    class _StubClient:
        async def complete(self, req: object) -> object:
            from harnessflow_worker.llm import LLMResponse

            return LLMResponse(
                model_used="claude-sonnet-4-6",
                text="0.8",
                input_tokens=1,
                output_tokens=1,
                cost_usd_cents=0,
                finish_reason="stop",
            )

    s = LLMJudge(client=_StubClient())  # type: ignore[arg-type]
    score = await s.score(
        Case(id="c", criteria="rubric"), RunOutcome(output="an answer")
    )
    assert score == 0.8


def test_load_dataset() -> None:
    cases = load_cases("research-assistant")
    assert len(cases) >= 8
    assert all(c.inputs.get("query") for c in cases)
    assert all(c.expected and c.criteria for c in cases)


def test_aggregate_means_and_percentiles() -> None:
    results = [
        CaseResult(
            case_id="a",
            scores={"exact_match": 1.0, "llm_judge": 0.5},
            outcome=RunOutcome(output="", latency_ms=100, cost_usd_cents=10),
        ),
        CaseResult(
            case_id="b",
            scores={"exact_match": 0.0, "llm_judge": 1.0},
            outcome=RunOutcome(output="", latency_ms=300, cost_usd_cents=20),
        ),
    ]
    report = aggregate("wf", "ds", 1, results)
    means = {q.scorer: q.mean for q in report.quality}
    assert means["exact_match"] == 0.5
    assert means["llm_judge"] == 0.75
    assert report.cost_total_usd_cents == 30
    assert report.overall_score == pytest.approx(0.625)
    assert report.latency_p95_ms == 300
