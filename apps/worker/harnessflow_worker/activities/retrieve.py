"""``retrieve`` activity — Week-3 stub.

Returns a canned response that includes the configured source and top_k so
the demo workflow can chain a retriever step into a downstream LLM call.
ChromaDB-backed retrieval lands in Week 4 alongside the demo corpus.
"""

from __future__ import annotations

from temporalio import activity

from harnessflow_worker.activities._common import ActivityFn, Deps, with_persistence
from harnessflow_worker.types import ActivityInput, ActivityResult


def make_retrieve(deps: Deps) -> ActivityFn:
    @activity.defn(name="retrieve")
    async def retrieve(in_: ActivityInput) -> ActivityResult:
        async def body() -> ActivityResult:
            step = in_.step
            source = step.source or "(unset)"
            top_k = step.top_k
            text = f"[stub-retrieve source={source} top_k={top_k}]"
            return ActivityResult(output=text)

        return await with_persistence(deps, in_, body)

    return retrieve
