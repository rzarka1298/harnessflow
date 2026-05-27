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


def evaluate_gate(
    report: EvalReport,
    baseline: EvalReport | None,
    max_regression: float,
) -> GateResult:
    """Compare ``report`` to ``baseline`` and flag any scorer whose mean
    dropped by more than ``max_regression``.

    - ``baseline is None`` (e.g. a workflow added for the first time in this
      PR) passes the gate — there is nothing to regress against.
    - ``max_regression`` is the allowed downward delta. A scorer fails the
      gate when ``current < baseline - max_regression``. Pass ``0.0`` to
      forbid any drop; pass a larger value to allow noise.
    - Scorers present in ``report`` but missing from ``baseline`` are
      ignored — they're new, not regressed.
    """
    if baseline is None:
        return GateResult(passed=True, max_regression_allowed=max_regression)

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
    lines = [
        f"❌ **Regression — {len(result.regressions)} scorer(s) dropped beyond the "
        f"allowed `{result.max_regression_allowed:.3f}` threshold:**",
        "",
        "| Scorer | Baseline | Current | Δ |",
        "| --- | --- | --- | --- |",
    ]
    for r in result.regressions:
        lines.append(
            f"| {r.scorer} | {r.baseline:.3f} | {r.current:.3f} | {r.delta:+.3f} |"
        )
    return "\n".join(lines)
