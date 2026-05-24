"""CLI: run an eval suite against a workflow and print a report.

    uv run harnessflow-eval --workflow-id <id> --dataset research-assistant
"""

from __future__ import annotations

import argparse
import asyncio
import os

from harnessflow_eval.dataset import load_cases
from harnessflow_eval.report import aggregate
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
    return p.parse_args()


async def _amain() -> None:
    args = _build_args()
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

    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(render_markdown(report))


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
