"""llm_judge scorer — asks a judge model to rate, 0-1, how well the output
satisfies the case's criteria (or reference answer). Reuses the worker's
in-house LLMClient; in mock mode (no keys) the judge returns a deterministic
mid score so the pipeline still runs offline."""

from __future__ import annotations

import re

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

_NUM = re.compile(r"[01](?:\.\d+)?")


class LLMJudge:
    name = "llm_judge"

    def __init__(self, client: LLMClient | None = None) -> None:
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
        m = _NUM.search(rsp.text)
        if not m:
            # Mock provider returns canned text with no number — treat as a
            # neutral 0.5 so offline runs produce a usable score.
            return 0.5
        return max(0.0, min(1.0, float(m.group())))
