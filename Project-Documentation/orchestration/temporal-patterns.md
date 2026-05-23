# Temporal patterns in HarnessFlow

How HarnessFlow uses Temporal, and the determinism rules that make it safe.
Companion to [orchestration/overview.md](./overview.md) and
[ADR-0001](../decisions/0001-use-temporal-not-custom-orchestrator.md).

## The model: one generic workflow interpreting an IR

We do **not** generate a Temporal workflow per user workflow. There is a single
registered workflow function, `HarnessFlowWorkflow` (Go,
`apps/api/internal/workflow/compiler.go`), that takes the parsed DSL as input
and executes its steps in topological order by dispatching activities by name.
Adding a workflow is data (YAML), not code. The trade-off — slightly more
runtime branching vs. zero codegen-per-workflow and one thing to test — is the
right one for a platform.

## Determinism contract

Temporal replays workflow code from history after a worker crash, so the code
**must be deterministic**: same history ⇒ same sequence of commands. Concretely,
inside `HarnessFlowWorkflow` we never:

- read wall-clock time (`time.Now()`), use RNG, or do direct I/O — all of that
  lives in activities;
- iterate a Go `map` (non-deterministic order). The step order is a
  pre-computed slice (`Input.Order`) from the parser's Kahn topological sort;
  the workflow only indexes the map by name.

All side effects (LLM calls, DB writes, retrieval) are activities. The workflow
is pure orchestration.

## Polyglot worker split

Two workers register against the same task queue `harnessflow-tasks`:

- **Go** (`apps/api`) registers only the *workflow* function, with
  `worker.Options{LocalActivityWorkerOnly: true}` so it does not poll for
  activity tasks it can't run.
- **Python** (`apps/worker`) registers the *activities*
  (`llm_call`, `retrieve`, `tool_call`, `verify`, `record_run_status`).

Temporal routes workflow tasks to the Go worker and activity tasks to the
Python worker by task type. Activity names are the wire contract
(`activity_names.go` ↔ the Python `@activity.defn(name=...)`); changing them is
breaking and needs an ADR. The Pydantic data converter on the Python side and
JSON-tagged Go structs keep the payloads compatible.

## Retries

Per-step `retry_policy.max_attempts` maps to a Temporal `RetryPolicy` in
`activityOptionsFor` (exponential backoff, default 3 attempts). This is
Temporal-level activity retry — distinct from the LLMClient's *model fallback*,
which is in-process within a single activity attempt.

## Signals: human approval gates

A step with `requires_approval: true` pauses the workflow:
`recordStatus(waiting_approval)` then
`workflow.GetSignalChannel(ctx, "approve").Receive(ctx, &sig)` blocks
deterministically until the API calls `client.SignalWorkflow(..., "approve", ...)`
(via `RunService.ApproveRun`). Signals are durable and survive worker restarts —
the correct primitive for an open-ended human wait. On signal the run flips back
to `running` and proceeds.

## Run lifecycle persistence

The workflow brackets its steps with the `record_run_status` activity
(`running` → `completed`/`failed`), best-effort so a status-write failure never
changes the run's real outcome. This is how `workflow_runs.status` and the
duration metric get written despite the workflow itself doing no I/O.

## Tracing across the boundary

The Temporal Go and Python SDK OpenTelemetry interceptors propagate W3C trace
context across the workflow↔activity boundary, so a single trace spans
`Connect RPC → StartWorkflow → workflow → activity → LLM call` across both
languages. Verified in Jaeger (see observability docs).
