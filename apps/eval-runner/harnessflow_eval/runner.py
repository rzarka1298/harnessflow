"""EvalRunner — drives a workflow over a dataset via the Connect HTTP API and
scores each case. Decoupled from Temporal: it speaks the same Connect/JSON
endpoints the dashboard uses, so it needs nothing beyond a running api+worker."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

from harnessflow_eval.report import EvalReport, aggregate
from harnessflow_eval.scorers.base import Scorer
from harnessflow_eval.types import Case, CaseResult, RunOutcome

log = structlog.get_logger()

_RUN_WORKFLOW = "/harnessflow.workflow.v1.WorkflowService/RunWorkflow"
_GET_RUN = "/harnessflow.run.v1.RunService/GetRun"

# Connect/protojson serializes proto enums as their string names, so we match
# RunStatus by name rather than ordinal.
_TERMINAL = {
    "RUN_STATUS_COMPLETED",
    "RUN_STATUS_FAILED",
    "RUN_STATUS_CANCELED",
}


class EvalRunner:
    def __init__(
        self,
        api_base_url: str,
        scorers: list[Scorer],
        *,
        poll_interval_s: float = 1.0,
        run_timeout_s: float = 120.0,
    ) -> None:
        self._base = api_base_url.rstrip("/")
        self._scorers = scorers
        self._poll = poll_interval_s
        self._timeout = run_timeout_s

    async def run(
        self, workflow_id: str, cases: list[Case], seeds_per_case: int = 1
    ) -> EvalReport:
        async with httpx.AsyncClient(base_url=self._base, timeout=30.0) as client:
            results = [
                await self._run_case(client, workflow_id, c, seeds_per_case)
                for c in cases
            ]
        return aggregate(workflow_id, "", seeds_per_case, results)

    async def _run_case(
        self, client: httpx.AsyncClient, workflow_id: str, case: Case, seeds: int
    ) -> CaseResult:
        outcomes: list[RunOutcome] = []
        seed_scores: list[dict[str, float]] = []
        for _ in range(max(1, seeds)):
            outcome = await self._run_once(client, workflow_id, case)
            outcomes.append(outcome)
            seed_scores.append(
                {s.name: await s.score(case, outcome) for s in self._scorers}
            )

        # Average scores + latency across seeds; cost is the per-run mean.
        mean_scores = {
            name: sum(d[name] for d in seed_scores) / len(seed_scores)
            for name in seed_scores[0]
        }
        mean_outcome = RunOutcome(
            output=outcomes[-1].output,
            latency_ms=sum(o.latency_ms for o in outcomes) // len(outcomes),
            cost_usd_cents=sum(o.cost_usd_cents for o in outcomes) // len(outcomes),
            status=outcomes[-1].status,
        )
        log.info("case scored", case=case.id, scores=mean_scores)
        return CaseResult(case_id=case.id, scores=mean_scores, outcome=mean_outcome)

    async def _run_once(
        self, client: httpx.AsyncClient, workflow_id: str, case: Case
    ) -> RunOutcome:
        started = await client.post(
            _RUN_WORKFLOW,
            json={"workflow_id": workflow_id, "inputs": case.inputs},
            headers={"Connect-Protocol-Version": "1"},
        )
        started.raise_for_status()
        run_id = started.json()["runId"]

        waited = 0.0
        while True:
            got = await client.post(
                _GET_RUN, json={"id": run_id}, headers={"Connect-Protocol-Version": "1"}
            )
            got.raise_for_status()
            body = got.json()
            status = str(body["run"].get("status", ""))
            if status in _TERMINAL:
                return _outcome_from(body)
            if waited >= self._timeout:
                return RunOutcome(output="", status="timeout")
            await asyncio.sleep(self._poll)
            waited += self._poll


def _outcome_from(body: dict[str, Any]) -> RunOutcome:
    run = body["run"]
    steps = body.get("steps", [])
    # The "answer" is the last non-verify step's output; fall back to the last.
    answer = ""
    for s in steps:
        if s.get("type") != "verify" and s.get("outputPreview"):
            answer = s["outputPreview"]
    if not answer and steps:
        answer = steps[-1].get("outputPreview", "")
    # int64 fields are JSON strings under protojson; int() coerces them.
    latency = sum(int(s.get("latencyMs", 0)) for s in steps)
    status_map = {
        "RUN_STATUS_COMPLETED": "completed",
        "RUN_STATUS_FAILED": "failed",
        "RUN_STATUS_CANCELED": "canceled",
    }
    return RunOutcome(
        output=answer,
        latency_ms=latency,
        cost_usd_cents=int(run.get("totalCostUsdCents", 0)),
        status=status_map.get(str(run.get("status", "")), "unknown"),
    )
