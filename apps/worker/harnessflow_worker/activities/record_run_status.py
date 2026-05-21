"""``record_run_status`` activity — persists run lifecycle transitions.

Invoked by the Go workflow (not a DSL step): once with ``running`` at the
start, then once with ``completed`` or ``failed`` at the end. Closes the gap
where workflow_runs.status stayed ``pending`` after Temporal completion.

Run-level metric emission is layered on in the Week-5 metrics commit.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from temporalio import activity

from harnessflow_worker.activities._common import Deps
from harnessflow_worker.persistence import update_run_status
from harnessflow_worker.types import RunStatusInput

log = structlog.get_logger()

RunStatusFn = Callable[[RunStatusInput], Awaitable[None]]


def make_record_run_status(deps: Deps) -> RunStatusFn:
    @activity.defn(name="record_run_status")
    async def record_run_status(in_: RunStatusInput) -> None:
        duration_s = await update_run_status(
            deps.pool, in_.run_id, in_.status, error=in_.error
        )
        log.info(
            "run status recorded",
            run_id=in_.run_id,
            workflow=in_.workflow_name,
            status=in_.status,
            duration_s=duration_s,
        )

    return record_run_status
