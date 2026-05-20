"""``tool_call`` activity — Week-3 stub.

Returns a canned response describing the tools the workflow declared. Real
tool dispatch (against a whitelist) lands when we have a defined tool surface
— ADR pending.
"""

from __future__ import annotations

from temporalio import activity

from harnessflow_worker.activities._common import ActivityFn, Deps, with_persistence
from harnessflow_worker.types import ActivityInput, ActivityResult


def make_tool_call(deps: Deps) -> ActivityFn:
    @activity.defn(name="tool_call")
    async def tool_call(in_: ActivityInput) -> ActivityResult:
        async def body() -> ActivityResult:
            step = in_.step
            if not step.tools:
                raise ValueError("tool_call: 'tools' must be non-empty")
            text = f"[stub-tool-call tools={','.join(step.tools)}]"
            return ActivityResult(output=text)

        return await with_persistence(deps, in_, body)

    return tool_call
