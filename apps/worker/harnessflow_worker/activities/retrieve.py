"""``retrieve`` activity — ChromaDB-backed similarity search.

The corpus is seeded by ``scripts/seed-chroma.py`` from
``apps/worker/harnessflow_worker/retrieval/corpus.jsonl`` into the persistent
ChromaDB store at ``$HARNESSFLOW_CHROMA_PATH`` (default ``./data/chroma``).

The query text is sourced from the upstream planner step when present, else
from the workflow's ``query`` input. Hits are returned as a newline-separated
``[source] text`` block that the executor step can paste straight into its
prompt.
"""

from __future__ import annotations

import asyncio

from temporalio import activity

from harnessflow_worker.activities._common import ActivityFn, Deps, with_persistence
from harnessflow_worker.retrieval import query
from harnessflow_worker.types import ActivityInput, ActivityResult


def make_retrieve(deps: Deps) -> ActivityFn:
    @activity.defn(name="retrieve")
    async def retrieve(in_: ActivityInput) -> ActivityResult:
        async def body() -> ActivityResult:
            step = in_.step
            query_text = _resolve_query(in_)
            top_k = step.top_k or 5
            # ChromaDB's Python client is sync; run it on a worker thread so
            # we don't block the asyncio loop while embeddings compute.
            hits = await asyncio.to_thread(query, query_text, top_k)
            if not hits:
                return ActivityResult(output="(no documents retrieved)")
            rendered = "\n\n".join(f"[{h.source}] {h.text}" for h in hits)
            return ActivityResult(output=rendered)

        return await with_persistence(deps, in_, body)

    return retrieve


def _resolve_query(in_: ActivityInput) -> str:
    """Pick the freest, most-specific available query text.

    Order of preference:
      1. Output of the most-recent prior step (typically the planner).
      2. The workflow's ``query`` input.
      3. The step name as a degenerate fallback.
    """
    # prior_outputs is ordered by Python's dict insertion order, which the
    # workflow honors (topo-sorted execution); take the last inserted value.
    if in_.prior_outputs:
        last = next(reversed(in_.prior_outputs.values()))
        if last.output:
            return last.output
    if "query" in in_.run_inputs:
        return in_.run_inputs["query"]
    return in_.step_name
