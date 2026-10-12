"""Regression gate — compares an EvalReport against a baseline and decides
whether the new report should be allowed to merge.

This lives behind the eval-runner CLI's ``--baseline-json`` /
``--gate-max-regression`` flags and is consumed by ``.github/workflows/eval-gate.yml``.
The gate logic is intentionally pure so it's exercised in unit tests; the
CLI is the only thing that turns the result into an exit code.

We gate on per-scorer regression rather than the headline ``overall_score``
because the overall is an unweighted mean that can hide a catastrophic drop
in one scorer behind improvements elsewhere (the classic "judge says 1.0,
exact-match is zero" pathology).
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

from harnessflow_eval.report import EvalReport


class ScorerRegression(BaseModel):
    """One scorer that dropped by more than the allowed threshold."""

    scorer: str
    baseline: float
    current: float
    delta: float  # current - baseline; negative for a regression.


class GateResult(BaseModel):
    """Outcome of running the regression gate.

    ``passed=False`` is the signal the CI workflow turns into a nonzero exit.
    ``regressions`` always lists the offending scorers (empty when passed).
    """

    passed: bool
    max_regression_allowed: float
    regressions: list[ScorerRegression] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def evaluate_gate(
    report: EvalReport,
    baseline: EvalReport | None,
    max_regression: float,
) -> GateResult:
    """Compare ``report`` to ``baseline`` and flag any scorer whose mean
    dropped by more than ``max_regression``.

    - ``baseline is None`` (e.g. a workflow added for the first time in this
      PR) skips regression comparison but still requires valid case evidence.
    - ``max_regression`` is the allowed downward delta. A scorer fails the
      gate when ``current < baseline - max_regression``. Pass ``0.0`` to
      forbid any drop; pass a larger value to allow noise.
    - Scorers present in ``report`` but missing from ``baseline`` are
      ignored — they're new, not regressed.
    """
    if not math.isfinite(max_regression) or not 0 <= max_regression <= 1:
        raise ValueError("max_regression must be finite and between zero and one")

    errors: list[str] = []
    for label, candidate in [("current", report), ("baseline", baseline)]:
        if candidate is None:
            continue
        names = [q.scorer for q in candidate.quality]
        if not names or len(names) != len(set(names)):
            errors.append(f"{label}: missing or duplicate scorer aggregates")
        if candidate.case_count < 1 or len(candidate.case_results) != candidate.case_count:
            errors.append(f"{label}: missing case evidence")
        if candidate.seeds_per_case < 1:
            errors.append(f"{label}: invalid seed count")
        if any(not math.isfinite(q.mean) or not 0 <= q.mean <= 1 for q in candidate.quality):
            errors.append(f"{label}: invalid scorer aggregate")
        ids = [case.case_id for case in candidate.case_results]
        if len(ids) != len(set(ids)):
            errors.append(f"{label}: duplicate case IDs")
        for case in candidate.case_results:
            if case.outcome.status != "completed":
                errors.append(f"{label}: case {case.case_id} did not complete")
            if set(case.scores) != set(names) or any(
                not math.isfinite(value) or not 0 <= value <= 1 for value in case.scores.values()
            ):
                errors.append(f"{label}: case {case.case_id} has missing or invalid scores")
        if candidate.case_results:
            for score in candidate.quality:
                values = [case.scores.get(score.scorer) for case in candidate.case_results]
                if all(value is not None and math.isfinite(value) for value in values):
                    mean = sum(value for value in values if value is not None) / len(values)
                    if not math.isclose(score.mean, mean, rel_tol=1e-9, abs_tol=1e-9):
                        errors.append(
                            f"{label}: aggregate {score.scorer} does not match case evidence"
                        )

    if baseline is not None:
        missing = {q.scorer for q in baseline.quality} - {q.scorer for q in report.quality}
        errors.extend(f"current: missing baseline scorer {name}" for name in sorted(missing))
        if report.dataset != baseline.dataset or report.seeds_per_case != baseline.seeds_per_case:
            errors.append("current and baseline use different datasets or seed counts")
        if {case.case_id for case in report.case_results} != {
            case.case_id for case in baseline.case_results
        }:
            errors.append("current and baseline cover different cases")
    if errors or baseline is None:
        return GateResult(passed=not errors, max_regression_allowed=max_regression, errors=errors)

    base_by_name = {q.scorer: q.mean for q in baseline.quality}
    regressions: list[ScorerRegression] = []
    for q in report.quality:
        if q.scorer not in base_by_name:
            continue
        base = base_by_name[q.scorer]
        delta = q.mean - base
        if delta < -max_regression:
            regressions.append(
                ScorerRegression(
                    scorer=q.scorer,
                    baseline=base,
                    current=q.mean,
                    delta=delta,
                )
            )
    return GateResult(
        passed=not regressions,
        max_regression_allowed=max_regression,
        regressions=regressions,
    )


def render_gate_markdown(result: GateResult) -> str:
    """Render the gate verdict as a short markdown block, suitable for
    appending to the per-eval markdown report in a PR comment."""
    if result.passed:
        return "✅ **Gate passed.**"
    if result.errors:
        return "❌ **Gate failed: incomplete or invalid evaluation evidence.**\n\n" + "\n".join(
            f"- {error}" for error in result.errors
        )
    lines = [
        f"❌ **Regression — {len(result.regressions)} scorer(s) dropped beyond the "
        f"allowed `{result.max_regression_allowed:.3f}` threshold:**",
        "",
        "| Scorer | Baseline | Current | Δ |",
        "| --- | --- | --- | --- |",
    ]
    for r in result.regressions:
        lines.append(f"| {r.scorer} | {r.baseline:.3f} | {r.current:.3f} | {r.delta:+.3f} |")
    return "\n".join(lines)
