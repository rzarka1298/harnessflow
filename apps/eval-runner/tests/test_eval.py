"""Offline unit tests for scorers, dataset loading, and report aggregation.
The live runner (needs api+worker) is exercised separately."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from harnessflow_eval.dataset import load_cases
from harnessflow_eval.gate import evaluate_gate, render_gate_markdown
from harnessflow_eval.report import EvalReport, ScorerAggregate, aggregate
from harnessflow_eval.runner import EvalRunner
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
async def test_llm_judge_mock_is_neutral(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESSFLOW_MOCK", "1")
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
    score = await s.score(Case(id="c", criteria="rubric"), RunOutcome(output="an answer"))
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


# ---------------------------------------------------------------------------
# Regression gate
# ---------------------------------------------------------------------------


def _report_with(scores: dict[str, float]) -> EvalReport:
    """Build a minimal EvalReport with the given scorer aggregates — enough
    for the gate, which only reads ``quality``."""
    return EvalReport(
        workflow_id="wf",
        dataset="ds",
        seeds_per_case=1,
        case_count=1,
        quality=[ScorerAggregate(scorer=k, mean=v) for k, v in scores.items()],
        case_results=[
            CaseResult(
                case_id="c", scores=scores, outcome=RunOutcome(output="answer", status="completed")
            )
        ],
    )


def test_gate_no_baseline_always_passes() -> None:
    # New workflow: nothing to compare against.
    g = evaluate_gate(_report_with({"x": 0.0}), None, 0.05)
    assert g.passed
    assert g.regressions == []


def test_gate_passes_when_within_threshold() -> None:
    baseline = _report_with({"exact_match": 0.80, "llm_judge": 0.70})
    current = _report_with({"exact_match": 0.78, "llm_judge": 0.75})
    g = evaluate_gate(current, baseline, max_regression=0.05)
    assert g.passed
    assert g.regressions == []


def test_gate_fails_on_single_scorer_drop() -> None:
    baseline = _report_with({"exact_match": 0.80, "llm_judge": 0.70})
    current = _report_with({"exact_match": 0.50, "llm_judge": 0.75})
    g = evaluate_gate(current, baseline, max_regression=0.05)
    assert not g.passed
    assert len(g.regressions) == 1
    r = g.regressions[0]
    assert r.scorer == "exact_match"
    assert r.delta == pytest.approx(-0.30)
    md = render_gate_markdown(g)
    assert "Regression" in md and "exact_match" in md


def test_gate_ignores_new_scorers() -> None:
    # ``embedding_similarity`` is added in the PR; it can't have regressed.
    baseline = _report_with({"exact_match": 0.80})
    current = _report_with({"exact_match": 0.80, "embedding_similarity": 0.10})
    g = evaluate_gate(current, baseline, max_regression=0.05)
    assert g.passed


def test_gate_zero_threshold_forbids_any_drop() -> None:
    baseline = _report_with({"exact_match": 0.80})
    current = _report_with({"exact_match": 0.79})
    g = evaluate_gate(current, baseline, max_regression=0.0)
    assert not g.passed
    assert g.regressions[0].delta == pytest.approx(-0.01)


def test_gate_rejects_removed_scorer_even_when_remaining_scores_improve() -> None:
    baseline = _report_with({"exact_match": 0.8, "llm_judge": 0.7})
    current = _report_with({"exact_match": 1.0})
    result = evaluate_gate(current, baseline, 0.05)
    assert not result.passed
    assert "missing baseline scorer llm_judge" in " ".join(result.errors)
    assert "invalid evaluation evidence" in render_gate_markdown(result)


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -0.1, 1.1])
def test_gate_rejects_invalid_scores_without_a_baseline(score: float) -> None:
    assert not evaluate_gate(_report_with({"x": score}), None, 0.05).passed


def test_gate_rejects_missing_case_evidence_and_failed_runs() -> None:
    report = _report_with({"x": 1.0})
    report.case_results = []
    assert not evaluate_gate(report, None, 0.05).passed
    report = _report_with({"x": 1.0})
    report.case_results[0].outcome.status = "failed"
    assert not evaluate_gate(report, None, 0.05).passed
    report = _report_with({"x": 1.0})
    report.case_results[0].scores = {}
    assert not evaluate_gate(report, None, 0.05).passed


def test_gate_rejects_noncomparable_reports() -> None:
    baseline = _report_with({"x": 0.0})
    current = _report_with({"x": 1.0})
    current.case_results[0].case_id = "different"
    assert not evaluate_gate(current, baseline, 0.05).passed
    current = _report_with({"x": 1.0})
    current.dataset = "different"
    assert not evaluate_gate(current, baseline, 0.05).passed


def test_gate_rejects_aggregate_without_supporting_case_scores() -> None:
    report = _report_with({"x": 1.0})
    report.case_results[0].scores["x"] = 0.0
    assert not evaluate_gate(report, None, 0.05).passed


@pytest.mark.parametrize("threshold", [float("nan"), float("inf"), -1.0, 1.1])
def test_gate_rejects_invalid_threshold(threshold: float) -> None:
    with pytest.raises(ValueError, match="max_regression"):
        evaluate_gate(_report_with({"x": 1.0}), None, threshold)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["approved", "10", "-0.5", "1.1", "NaN", "inf", "Score: 0.8"])
async def test_judge_rejects_malformed_or_out_of_range_verdict(text: str) -> None:
    from harnessflow_worker.llm import LLMResponse

    client = AsyncMock()
    client.complete.return_value = LLMResponse(
        model_used="judge",
        text=text,
        input_tokens=1,
        output_tokens=1,
        cost_usd_cents=0,
        finish_reason="stop",
    )
    with pytest.raises(ValueError, match="judge"):
        await LLMJudge(client=client).score(
            Case(id="c", criteria="rubric"), RunOutcome(output="answer")
        )


@pytest.mark.asyncio
async def test_runner_does_not_score_a_failed_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = EvalRunner("http://localhost:8080", [])
    monkeypatch.setattr(
        runner, "_run_once", AsyncMock(return_value=RunOutcome(output="answer", status="failed"))
    )
    with pytest.raises(RuntimeError, match="did not complete"):
        await runner._run_case(AsyncMock(), "wf", Case(id="c"), 2)
