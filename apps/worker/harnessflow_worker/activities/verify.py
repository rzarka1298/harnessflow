"""``verify`` activity — LLM-as-judge over a prior step's output.

Reads ``criteria`` from the step (optional) and the concatenated outputs of
prior steps, asks the configured judge model "does this meet the criteria?",
and returns the verdict as the activity output. The retry-loop semantics
described in SPEC.md land in Week 6.
"""

from __future__ import annotations

from temporalio import activity

from harnessflow_worker.activities._common import ActivityFn, Deps, with_persistence
from harnessflow_worker.llm import LLMRequest
from harnessflow_worker.types import ActivityInput, ActivityResult

_JUDGE_MODEL = "claude-sonnet-4-6"

_JUDGE_PROMPT = """You are a strict reviewer of AI workflow outputs.

Criteria:
{criteria}

Output to evaluate:
{output}

Reply with exactly one word: PASS or FAIL. No other text."""


def make_verify(deps: Deps) -> ActivityFn:
    @activity.defn(name="verify")
    async def verify(in_: ActivityInput) -> ActivityResult:
        async def body() -> ActivityResult:
            criteria = in_.step.criteria or "The output is non-empty and on-topic."
            concatenated = "\n\n---\n\n".join(
                r.output for r in in_.prior_outputs.values() if r.output
            ) or "(no prior outputs)"
            rsp = await deps.llm.complete(
                LLMRequest(
                    model=_JUDGE_MODEL,
                    prompt=_JUDGE_PROMPT.format(criteria=criteria, output=concatenated),
                    max_tokens=8,
                    temperature=0.0,
                )
            )
            return ActivityResult(
                output=rsp.text.strip(),
                input_tokens=rsp.input_tokens,
                output_tokens=rsp.output_tokens,
                cost_usd_cents=rsp.cost_usd_cents,
            )

        return await with_persistence(deps, in_, body)

    return verify
