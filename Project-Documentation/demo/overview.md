# Demo — Overview

**Location:** `packages/examples/workflows/research-assistant.yaml`, `apps/eval-runner/harnessflow_eval/datasets/research-assistant.jsonl`, `scripts/seed-chroma.py`.

The "Research Assistant" is the canonical north-star demo workflow — everything (README, dashboard seed, eval suite, Loom video, blog posts) revolves around it. ONE shared example keeps the docs consistent and demoable.

## Workflow shape

```
        ┌────────────────────────────────────────────┐
        │              Research Assistant            │
        └────────────────────────────────────────────┘

  ┌────────┐   ┌───────────┐   ┌──────────┐   ┌─────────┐
  │planner ├──▶│ retriever ├──▶│ executor ├──▶│verifier │
  └────────┘   └───────────┘   └──────────┘   └─────────┘
       │                                          │
       │ retrieval_confidence < 0.5               │ retries: 3
       ▼                                          ▼
  ┌──────────────────┐                  ┌────────────────┐
  │ fallback_branch  │                  │ synthesis +    │
  │ (broader query)  │                  │ approval gate  │
  └──────────────────┘                  └────────────────┘
```

## Features exercised

| Feature | How |
| --- | --- |
| Multi-step DAG | 4 stages in topological order |
| Branching | `if retrieval_confidence < 0.5` triggers fallback retrieval |
| Retries | Verifier loops up to 3 times |
| Model fallback | OpenAI primary, Anthropic on rate-limit (declared per step) |
| Approval gate | `requires_approval: true` on synthesis when query is flagged sensitive |
| Eval | 30-case Q&A dataset, LLM-judge scoring |
| Observability | Full trace Go→Temporal→Python→OpenAI |

## Corpus

Seeded into ChromaDB by `scripts/seed-chroma.py`:

- ~20 chunks from Anthropic blog (Claude, agent design, AI safety)
- ~20 chunks from Temporal blog (workflows, signals, determinism)
- ~10 chunks from OpenTelemetry docs (semantic conventions, GenAI)

This is on-brand for the project and makes the demo questions feel curated rather than random.

## Sample queries (from `research-assistant.jsonl`)

- "How does Temporal handle workflow retries vs. activity retries?"
- "What does OpenTelemetry recommend for instrumenting LLM calls?"
- "Why did Anthropic introduce computer use in 2024?"

## Demo script (for the Loom video)

1. `make up` — show the docker-compose stack come up.
2. Open `localhost:3001` — landing page, click "Run demo."
3. Watch the DAG animate as the workflow progresses.
4. After completion, click into the run — show token/cost/latency per step.
5. Click "View in Jaeger" — show the unified trace across Go and Python.
6. Open Grafana — show the cost dashboard.
7. `make eval` — show the eval comparison table.
8. Open a PR with a regressed prompt — show the eval-gate blocking.

Total target: 2:00–2:30 for week 4 Loom, 5:00 for week 12 ship video.

## Code-review example (week 9, YAML-only)

`packages/examples/workflows/code-review.yaml` — shows the DSL handles a different shape (diff-loader → static-analysis → LLM-review → severity-classify → comment-formatter). Not implemented end-to-end; just demonstrates the DSL surface.

## TODO as we go

- [ ] Write the 30 ground-truth answers for the eval dataset
- [ ] Decide how to flag "sensitive" queries — keyword match? Classifier step? Start simple (regex on a small wordlist).
- [ ] Loom recording setup: terminal font, color theme, audio
