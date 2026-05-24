"""Persist an EvalReport to Postgres (eval_runs + eval_result_cases).

The eval-runner is the executor; the Go EvalService reads these rows. JSONB
columns are written as JSON text with explicit ::jsonb casts so asyncpg needs
no codec registration.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import asyncpg

from harnessflow_eval.report import EvalReport

_PREVIEW_MAX = 4000


async def persist_report(dsn: str, workflow_id: str, report: EvalReport) -> str:
    """Insert the report and return the new eval_run id."""
    eval_run_id = uuid.uuid4()
    aggregate = {q.scorer: q.mean for q in report.quality}

    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO eval_runs (
                    id, workflow_id, dataset, status, seeds_per_case,
                    overall_score, aggregate_scores, latency_p50_ms,
                    latency_p95_ms, cost_total_usd_cents, completed_at
                )
                VALUES ($1, $2, $3, 'completed', $4, $5, $6::jsonb, $7, $8, $9, $10)
                """,
                eval_run_id,
                uuid.UUID(workflow_id),
                report.dataset,
                report.seeds_per_case,
                report.overall_score,
                json.dumps(aggregate),
                report.latency_p50_ms,
                report.latency_p95_ms,
                report.cost_total_usd_cents,
                datetime.now(UTC),
            )
            for cr in report.case_results:
                await conn.execute(
                    """
                    INSERT INTO eval_result_cases (
                        id, eval_run_id, case_id, scores, output_preview,
                        latency_ms, cost_usd_cents
                    )
                    VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
                    """,
                    uuid.uuid4(),
                    eval_run_id,
                    cr.case_id,
                    json.dumps(cr.scores),
                    cr.outcome.output[:_PREVIEW_MAX],
                    cr.outcome.latency_ms,
                    cr.outcome.cost_usd_cents,
                )
    finally:
        await conn.close()
    return str(eval_run_id)
