"""Temporal boundary. Logical blockers are data; infrastructure failures retry."""

from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from pathlib import Path
from typing import Any

import asyncpg
from temporalio import activity

from harnessflow_worker.projects.engine import tick
from harnessflow_worker.projects.store import ProjectStore


def make_project_tick(pool: asyncpg.Pool) -> Any:
    @activity.defn(name="project_tick")
    async def project_tick(arg: dict[str, str]) -> dict[str, str]:
        store = ProjectStore(pool, arg["run_id"])
        root = Path(
            os.environ.get("HARNESSFLOW_DATA_DIR", "~/.local/share/harnessflow")
        ).expanduser()

        async def pulse() -> None:
            while True:
                activity.heartbeat(arg["run_id"])
                await asyncio.sleep(3)

        pulsing = asyncio.create_task(pulse())
        try:
            return await tick(store, root, heartbeat=lambda: activity.heartbeat(arg["run_id"]))
        finally:
            pulsing.cancel()
            with suppress(asyncio.CancelledError):
                await pulsing

    return project_tick
