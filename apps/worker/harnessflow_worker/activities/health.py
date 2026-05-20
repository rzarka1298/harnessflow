"""Stub `harnessflow_health` activity used to anchor the worker process during
Week-3 bootstrap. Not invoked by the demo workflow; it exists so the Temporal
worker has something to register before the real activities land in commit 3.
"""

from __future__ import annotations

import structlog
from temporalio import activity

log = structlog.get_logger()


@activity.defn(name="harnessflow_health")
async def health() -> str:
    log.info("health activity invoked")
    return "ok"
