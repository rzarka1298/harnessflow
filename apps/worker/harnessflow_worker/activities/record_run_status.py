"""``record_run_status`` activity — persists run lifecycle transitions.

Invoked by the Go workflow (not a DSL step): once with ``running`` at the
start, then once with ``completed`` or ``failed`` at the end. Closes the gap
where workflow_runs.status stayed ``pending`` after Temporal completion.

Also emits run-level metrics (count + duration) on terminal transitions.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from temporalio import activity

from harnessflow_worker.activities._common import Deps
from harnessflow_worker.events import (
    RUN_COMPLETED,
    RUN_FAILED,
    RUN_STARTED,
    WorkflowEvent,
)
from harnessflow_worker.metrics import record_run
from harnessflow_worker.persistence import update_run_status
from harnessflow_worker.types import RunStatusInput

log = structlog.get_logger()

RunStatusFn = Callable[[RunStatusInput], Awaitable[None]]

# Maps the persisted run status to the firehose event type. "running" is the
# start signal; the rest are terminal.
_EVENT_FOR_STATUS = {
    "running": RUN_STARTED,
    "completed": RUN_COMPLETED,
    "failed": RUN_FAILED,
}


def make_record_run_status(deps: Deps) -> RunStatusFn:
    @activity.defn(name="record_run_status")
    async def record_run_status(in_: RunStatusInput) -> None:
        duration_s = await update_run_status(deps.pool, in_.run_id, in_.status, error=in_.error)
        # Count + time only terminal transitions — counting "running" would
        # double every run.
        if in_.status != "running":
            record_run(in_.workflow_name, in_.status, duration_s)
        event_type = _EVENT_FOR_STATUS.get(in_.status)
        if event_type is not None:
            await deps.events.emit(
                WorkflowEvent(
                    event_type=event_type,
                    run_id=in_.run_id,
                    workflow_name=in_.workflow_name,
                    workflow_version=in_.workflow_version or None,
                    status=in_.status,
                    duration_s=duration_s,
                    error=in_.error or None,
                )
            )
        log.info(
            "run status recorded",
            run_id=in_.run_id,
            workflow=in_.workflow_name,
            status=in_.status,
            duration_s=duration_s,
        )

    return record_run_status
