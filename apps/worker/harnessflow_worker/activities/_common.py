"""Shared activity scaffolding — DI container + a timing/persistence wrapper
so each activity body stays focused on its step-type logic.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import asyncpg
import structlog

from harnessflow_worker.llm import LLMClient
from harnessflow_worker.persistence import step_completed, step_failed, step_started
from harnessflow_worker.types import ActivityInput, ActivityResult

log = structlog.get_logger()


# Activities are async functions of (ActivityInput) -> ActivityResult.
# Aliased here so the make_* factories have a clean return annotation.
ActivityFn = Callable[[ActivityInput], Awaitable[ActivityResult]]


@dataclass
class Deps:
    """Process-wide dependencies activities share."""

    pool: asyncpg.Pool
    llm: LLMClient


async def with_persistence(
    deps: Deps,
    activity_input: ActivityInput,
    body: Callable[[], Awaitable[ActivityResult]],
) -> ActivityResult:
    """Wrap an activity body with start/complete/failed persistence + timing.

    The body returns an ActivityResult; we time it, persist the row, and
    re-raise on exception (after marking the row failed) so Temporal's retry
    policy still observes failure correctly.
    """
    step_id = await step_started(
        deps.pool,
        activity_input.run_id,
        activity_input.step_name,
        activity_input.step.type,
    )
    start = time.monotonic()
    try:
        result = await body()
    except Exception as e:
        latency = int((time.monotonic() - start) * 1000)
        await step_failed(deps.pool, step_id, latency_ms=latency, error=str(e))
        log.exception(
            "step failed",
            step=activity_input.step_name,
            type=activity_input.step.type,
            latency_ms=latency,
        )
        raise

    latency = int((time.monotonic() - start) * 1000)
    await step_completed(
        deps.pool,
        step_id,
        latency_ms=latency,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd_cents=result.cost_usd_cents,
    )
    log.info(
        "step ok",
        step=activity_input.step_name,
        type=activity_input.step.type,
        latency_ms=latency,
        cost_cents=result.cost_usd_cents,
    )
    return result
