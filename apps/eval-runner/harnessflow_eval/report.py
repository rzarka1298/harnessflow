"""Eval report aggregation."""

from __future__ import annotations

from pydantic import BaseModel, Field

from harnessflow_eval.types import CaseResult


class ScorerAggregate(BaseModel):
    scorer: str
    mean: float


class EvalReport(BaseModel):
    workflow_id: str
    dataset: str
    seeds_per_case: int
    case_count: int
    quality: list[ScorerAggregate] = Field(default_factory=list)
    latency_p50_ms: int = 0
    latency_p95_ms: int = 0
    cost_total_usd_cents: int = 0
    case_results: list[CaseResult] = Field(default_factory=list)

    @property
    def overall_score(self) -> float:
        """Unweighted mean of the quality-scorer means — the single number the
        deployment gate compares against `requires_eval_pass.min_score`."""
        if not self.quality:
            return 0.0
        return sum(q.mean for q in self.quality) / len(self.quality)


def _percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    # Nearest-rank percentile.
    k = max(0, min(len(s) - 1, round(p / 100 * (len(s) - 1))))
    return s[k]


def aggregate(
    workflow_id: str,
    dataset: str,
    seeds_per_case: int,
    results: list[CaseResult],
) -> EvalReport:
    """Roll per-case results into an EvalReport."""
    scorer_names: list[str] = []
    for r in results:
        for name in r.scores:
            if name not in scorer_names:
                scorer_names.append(name)

    quality = [
        ScorerAggregate(
            scorer=name,
            mean=(
                sum(r.scores.get(name, 0.0) for r in results) / len(results)
                if results
                else 0.0
            ),
        )
        for name in scorer_names
    ]
    latencies = [r.outcome.latency_ms for r in results]
    return EvalReport(
        workflow_id=workflow_id,
        dataset=dataset,
        seeds_per_case=seeds_per_case,
        case_count=len(results),
        quality=quality,
        latency_p50_ms=_percentile(latencies, 50),
        latency_p95_ms=_percentile(latencies, 95),
        cost_total_usd_cents=sum(r.outcome.cost_usd_cents for r in results),
        case_results=results,
    )
