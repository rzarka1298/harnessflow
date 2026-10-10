"""llm_judge scorer — asks a judge model to rate, 0-1, how well the output
satisfies the case's criteria (or reference answer). Reuses the worker's
in-house LLMClient; in explicit mock mode the judge returns a deterministic
mid score so the pipeline still runs offline."""

from __future__ import annotations

import math
import os

from harnessflow_worker.llm import LLMClient, LLMRequest, build_default_client

from harnessflow_eval.types import Case, RunOutcome

_JUDGE_MODEL = "claude-sonnet-4-6"

_PROMPT = """You are grading an AI workflow's answer.

Reference / criteria:
{reference}

Answer to grade:
{answer}

Reply with ONLY a number from 0.0 to 1.0 (one decimal) rating how well the
answer satisfies the reference/criteria. No other text."""


class LLMJudge:
    name = "llm_judge"

    def __init__(self, client: LLMClient | None = None) -> None:
        self._mock = client is None and os.getenv("HARNESSFLOW_MOCK") == "1"
        self._client = client or build_default_client()

    async def score(self, case: Case, outcome: RunOutcome) -> float:
        reference = case.criteria or case.expected
        if not reference or not outcome.output:
            return 0.0
        rsp = await self._client.complete(
            LLMRequest(
                model=_JUDGE_MODEL,
                prompt=_PROMPT.format(reference=reference, answer=outcome.output),
                max_tokens=8,
                temperature=0.0,
            )
        )
        if self._mock:
            return 0.5
        try:
            score = float(rsp.text.strip())
        except ValueError as exc:
            raise ValueError("judge must return only a numeric score in [0, 1]") from exc
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("judge score must be finite and in [0, 1]")
        return score
