"""Project snapshots live in Postgres; large process transcripts remain local artifacts."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import asyncpg


class ProjectStore:
    def __init__(self, pool: asyncpg.Pool, run_id: str) -> None:
        self.pool = pool
        self.run_id = UUID(run_id)

    async def load(self) -> dict[str, Any]:
        row = await self.pool.fetchrow(
            """SELECT r.*, p.prd, p.name FROM project_runs r
               JOIN projects p ON p.id=r.project_id WHERE r.id=$1""",
            self.run_id,
        )
        if row is None:
            raise ValueError("project run not found")
        value = dict(row)
        value["state"] = (
            json.loads(value["state"]) if isinstance(value["state"], str) else value["state"]
        )
        return value

    async def save(self, state: dict[str, Any], status: str, reason: str = "") -> str:
        actual = await self.pool.fetchval(
            """UPDATE project_runs SET state=$2::jsonb,
               status=CASE WHEN $3 IN ('completed','blocked','exhausted') AND control='cancel'
                           THEN 'canceled'
                           WHEN $3 IN ('completed','blocked','exhausted') AND control='pause'
                           THEN 'paused' ELSE $3 END,
               reason=CASE WHEN $3 IN ('completed','blocked','exhausted')
                                AND control IN ('cancel','pause')
                           THEN 'Stopped by user request' ELSE $4 END, updated_at=NOW()
               WHERE id=$1 AND (status NOT IN ('completed','failed','canceled') OR status=$3)
               RETURNING status""",
            self.run_id,
            json.dumps(state),
            status,
            reason[:8000],
        )
        if actual is None:
            actual = await self.pool.fetchval(
                "SELECT status FROM project_runs WHERE id=$1", self.run_id
            )
        return str(actual)

    async def consume_control(self, control: str, version: int) -> None:
        await self.pool.execute(
            "UPDATE project_runs SET control='' WHERE id=$1 AND control=$2 AND control_version=$3",
            self.run_id,
            control,
            version,
        )
