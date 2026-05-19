# HarnessFlow Workflow DSL — Specification

The HarnessFlow workflow DSL is a YAML format describing an AI workflow as a
directed acyclic graph of steps. The machine-readable schema is
[`packages/sdk/schema/workflow.schema.json`](../sdk/schema/workflow.schema.json)
(JSON Schema draft 2020-12) — this document is its prose companion.

> **Changing the DSL requires an ADR.** See `Project-Documentation/decisions/`.
> The schema and this spec must change together, in the same commit.

## Top-level structure

```yaml
name: research-assistant      # required — kebab-case identifier
version: 1                    # required — integer >= 1
description: Plans, retrieves, executes, and verifies an answer.
steps:                        # required — at least one step
  planner: { ... }
  retriever: { ... }
deployment: { ... }           # optional
```

| Field | Required | Notes |
| --- | --- | --- |
| `name` | yes | Kebab-case, 1–64 chars, matches `^[a-z][a-z0-9-]*$`. |
| `version` | yes | Integer ≥ 1. Bumped by the author when the definition changes. |
| `description` | no | Free text, ≤ 500 chars. |
| `steps` | yes | Map of step name → step. Step names are kebab-case. |
| `deployment` | no | Deployment gating — see below. |

## Steps

Each step compiles to one Temporal activity. The execution order is derived
from the `after` edges, which must form a DAG (no cycles).

### Common step fields

| Field | Applies to | Notes |
| --- | --- | --- |
| `type` | all | One of `llm_call`, `retrieve`, `tool_call`, `verify`. Required. |
| `after` | all | List of step names that must finish first. Absent ⇒ root step. |
| `requires_approval` | all | If true, the run pauses on a human approval gate before this step. |
| `retry_policy` | all | See *Retry policy* below. |

### `llm_call`

Calls an LLM via the worker's `LLMClient`.

| Field | Required | Notes |
| --- | --- | --- |
| `model` | yes | Primary model id, e.g. `gpt-4o`, `claude-sonnet-4-6`. |
| `prompt` | yes | Prompt template; may reference workflow inputs and prior step outputs. |
| `fallback_on_rate_limit` | no | Model to retry with on a provider rate-limit error. |
| `fallback_on_5xx` | no | Model to retry with on a provider 5xx error. |
| `temperature` | no | Sampling temperature, 0–2. |
| `max_tokens` | no | Max output tokens. |

### `retrieve`

Retrieves documents from a vector store.

| Field | Required | Notes |
| --- | --- | --- |
| `source` | yes | Retrieval source id, e.g. `vector-db`. |
| `top_k` | no | Number of documents to return. Default 5. |

### `tool_call`

Invokes whitelisted tools.

| Field | Required | Notes |
| --- | --- | --- |
| `tools` | yes | Non-empty list of whitelisted tool names. |

### `verify`

Checks a prior step's output against criteria, with a bounded retry loop.

| Field | Required | Notes |
| --- | --- | --- |
| `criteria` | no | Natural-language description of a passing result. |

> Cross-field requirements (e.g. `llm_call` needs `model` and `prompt`) are
> validated by the orchestrator's compiler, not by the JSON Schema, which only
> checks structure and types.

## Retry policy

```yaml
retry_policy:
  type: static            # static | learned   (default: static)
  max_attempts: 3         # 1–10  (default: 3)
  fallback_to_static: true  # learned only — default true
```

- `static` — Temporal `RetryPolicy` with `max_attempts`.
- `learned` — the retry decision is resolved at runtime by the policy-learner
  service (Week 13). `fallback_to_static` controls behavior when no learned
  policy exists yet.

## Deployment gating

```yaml
deployment:
  requires_eval_pass:
    min_score: 0.85
```

When `requires_eval_pass` is set, the orchestrator refuses to activate the
workflow unless its most recent eval run scored at least `min_score` (0.0–1.0).

## Full example

```yaml
name: research-assistant
version: 1
description: Plans, retrieves, executes, and verifies an answer.
steps:
  planner:
    type: llm_call
    model: gpt-4o
    fallback_on_rate_limit: claude-sonnet-4-6
    prompt: |
      Break the user question into retrieval sub-queries.
  retriever:
    type: retrieve
    source: vector-db
    top_k: 8
    after: [planner]
  executor:
    type: llm_call
    model: gpt-4o
    prompt: |
      Answer the question using the retrieved context.
    after: [retriever]
  verifier:
    type: verify
    criteria: The answer is grounded in the retrieved context and cites it.
    retry_policy:
      type: static
      max_attempts: 3
    after: [executor]
deployment:
  requires_eval_pass:
    min_score: 0.85
```
