"""CLI: run an eval suite against a workflow and print a report.

    uv run harnessflow-eval --workflow-id <id> --dataset research-assistant

In CI (see ``.github/workflows/eval-gate.yml``) the same CLI is used twice
per changed workflow YAML — first against the baseline (writing the report
out with ``--out-json``), then against the PR version with
``--baseline-json`` + ``--gate-max-regression`` so the markdown picks up
deltas and the process exit-code reflects the gate verdict.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from harnessflow_eval.dataset import load_cases
from harnessflow_eval.gate import evaluate_gate, render_gate_markdown
from harnessflow_eval.report import EvalReport, aggregate
from harnessflow_eval.reporters import render_markdown
from harnessflow_eval.runner import EvalRunner
from harnessflow_eval.scorers import EmbeddingSimilarity, ExactMatch, LLMJudge, Scorer


def _build_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="harnessflow-eval")
    p.add_argument("--workflow-id", required=True)
    p.add_argument("--dataset", default="research-assistant")
    p.add_argument("--seeds", type=int, default=1)
    p.add_argument(
        "--api-base-url",
        default=os.getenv("HARNESSFLOW_API_BASE_URL", "http://localhost:8080"),
    )
    p.add_argument("--format", choices=["md", "json"], default="md")
    p.add_argument(
        "--database-url",
        default=os.getenv(
            "DATABASE_URL",
            "postgres://harnessflow:harnessflow@localhost:5432/harnessflow",
        ),
    )
    p.add_argument(
        "--no-persist",
        action="store_true",
        help="Skip writing the eval run to Postgres.",
    )
    p.add_argument(
        "--baseline-json",
        type=Path,
        default=None,
        help=(
            "Path to a previously emitted EvalReport JSON (see --out-json). "
            "When set, the markdown output includes a Δ-vs-baseline column "
            "and the regression gate is enabled."
        ),
    )
    p.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="Also write the JSON report to this path (useful for CI baseline capture).",
    )
    p.add_argument(
        "--out-md",
        type=Path,
        default=None,
        help="Also write the markdown report (+ gate verdict) to this path.",
    )
    p.add_argument(
        "--gate-max-regression",
        type=float,
        default=None,
        help=(
            "Fail (exit 1) if any scorer's mean dropped by more than this delta "
            "vs the baseline. Requires --baseline-json. Pass 0.0 to forbid any drop."
        ),
    )
    return p.parse_args()


async def _amain() -> int:
    args = _build_args()

    if args.gate_max_regression is not None and args.baseline_json is None:
        print(
            "error: --gate-max-regression requires --baseline-json",
            file=sys.stderr,
        )
        return 2

    cases = load_cases(args.dataset)
    scorers: list[Scorer] = [ExactMatch(), EmbeddingSimilarity(), LLMJudge()]
    runner = EvalRunner(args.api_base_url, scorers)
    report = await runner.run(args.workflow_id, cases, seeds_per_case=args.seeds)
    # Stamp the dataset name (runner leaves it blank).
    report = aggregate(args.workflow_id, args.dataset, args.seeds, report.case_results)

    if not args.no_persist:
        from harnessflow_eval.eval_store import persist_report

        eval_run_id = await persist_report(args.database_url, args.workflow_id, report)
        print(f"eval_run_id: {eval_run_id}")

    baseline: EvalReport | None = None
    if args.baseline_json is not None:
        baseline = EvalReport.model_validate_json(args.baseline_json.read_text())

    md = render_markdown(report, baseline)
    gate_md = ""
    exit_code = 0
    if args.gate_max_regression is not None:
        # baseline is guaranteed non-None here by the arg-validation above.
        gate = evaluate_gate(report, baseline, args.gate_max_regression)
        gate_md = "\n\n" + render_gate_markdown(gate)
        if not gate.passed:
            exit_code = 1

    if args.out_json is not None:
        args.out_json.write_text(report.model_dump_json(indent=2))
    if args.out_md is not None:
        args.out_md.write_text(md + gate_md + "\n")

    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(md + gate_md)

    return exit_code


def main() -> None:
    sys.exit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()
