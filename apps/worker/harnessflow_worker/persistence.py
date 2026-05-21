"""workflow_steps persistence — idempotent on Temporal retry.

Step ids are deterministic UUIDv5(namespace, "<run_id>/<step_name>") so a
retried activity invocation upserts the same row instead of inserting a
duplicate. This is enough for Week 3; attempt-count tracking lands in Week 6
alongside the proper retry-policy work.
"""

from __future__ import annotations

import uuid

import asyncpg

# Random v4 chosen once for the HarnessFlow namespace; do not change.
_NAMESPACE = uuid.UUID("4f7b2a1c-1d2e-4f3a-8b6c-9e0f1a2b3c4d")


def step_uuid(run_id: str, step_name: str) -> uuid.UUID:
    """Deterministic step id for a (run, step) pair."""
    return uuid.uuid5(_NAMESPACE, f"{run_id}/{step_name}")


async def step_started(
    pool: asyncpg.Pool,
    run_id: str,
    step_name: str,
    step_type: str,
) -> uuid.UUID:
    """Mark step as running. Inserts on first call, resets on retry."""
    step_id = step_uuid(run_id, step_name)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO workflow_steps (id, run_id, name, type, status, started_at)
            VALUES ($1, $2, $3, $4, 'running', NOW())
            ON CONFLICT (id) DO UPDATE
                SET status = 'running',
                    started_at = EXCLUDED.started_at,
                    ended_at = NULL,
                    error = ''
            """,
            step_id,
            uuid.UUID(run_id),
            step_name,
            step_type,
        )
    return step_id


async def step_completed(
    pool: asyncpg.Pool,
    step_id: uuid.UUID,
    *,
    latency_ms: int,
    input_tokens: int,
    output_tokens: int,
    cost_usd_cents: int,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE workflow_steps
            SET status = 'completed',
                ended_at = NOW(),
                latency_ms = $2,
                input_tokens = $3,
                output_tokens = $4,
                cost_usd_cents = $5
            WHERE id = $1
            """,
            step_id,
            latency_ms,
            input_tokens,
            output_tokens,
            cost_usd_cents,
        )


async def step_failed(
    pool: asyncpg.Pool,
    step_id: uuid.UUID,
    *,
    latency_ms: int,
    error: str,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE workflow_steps
            SET status = 'failed',
                ended_at = NOW(),
                latency_ms = $2,
                error = $3
            WHERE id = $1
            """,
            step_id,
            latency_ms,
            error,
        )


async def update_run_status(
    pool: asyncpg.Pool,
    run_id: str,
    status: str,
    *,
    error: str = "",
) -> float | None:
    """Persist a run's lifecycle transition.

    On "running", stamps started_at (idempotently). On a terminal status,
    stamps ended_at. Returns the run's wall-clock duration in seconds once the
    run is terminal (so the caller can emit a duration metric), else None.
    """
    terminal = status in ("completed", "failed", "canceled")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE workflow_runs
            SET status = $2,
                started_at = CASE WHEN $2 = 'running'
                                  THEN COALESCE(started_at, NOW())
                                  ELSE started_at END,
                ended_at = CASE WHEN $3 THEN NOW() ELSE ended_at END,
                error = $4
            WHERE id = $1
            RETURNING started_at, ended_at
            """,
            uuid.UUID(run_id),
            status,
            terminal,
            error,
        )
    if row and terminal and row["started_at"] and row["ended_at"]:
        return float((row["ended_at"] - row["started_at"]).total_seconds())
    return None
