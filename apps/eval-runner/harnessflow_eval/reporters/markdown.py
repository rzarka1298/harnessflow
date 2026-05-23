"""Render an EvalReport as markdown — used for CLI output and (Week 8) PR
comparison comments. Optionally diffs against a baseline report."""

from __future__ import annotations

from harnessflow_eval.report import EvalReport


def render_markdown(report: EvalReport, baseline: EvalReport | None = None) -> str:
    lines: list[str] = []
    lines.append(f"### Eval: `{report.dataset or report.workflow_id}`")
    lines.append("")
    lines.append(
        f"{report.case_count} cases x {report.seeds_per_case} seed(s) · "
        f"overall **{report.overall_score:.3f}**"
    )
    lines.append("")

    base_by_name = {q.scorer: q.mean for q in baseline.quality} if baseline else {}
    lines.append("| Scorer | Score | Δ vs base |")
    lines.append("| --- | --- | --- |")
    for q in report.quality:
        delta = ""
        if q.scorer in base_by_name:
            d = q.mean - base_by_name[q.scorer]
            delta = f"{d:+.3f}"
        lines.append(f"| {q.scorer} | {q.mean:.3f} | {delta or '—'} |")

    lines.append("")
    lines.append(
        f"latency p50 **{report.latency_p50_ms} ms** · p95 **{report.latency_p95_ms} ms** "
        f"· total cost **${report.cost_total_usd_cents / 100:.4f}**"
    )
    return "\n".join(lines)
