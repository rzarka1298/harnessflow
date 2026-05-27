# Evals — Overview

> **Status (Week 7, near complete).** The eval *runner* is built: `apps/eval-runner/`
> with three quality scorers, the `research-assistant.jsonl` dataset, the
> httpx-based runner, markdown/JSON reporters, a CLI, and unit tests. Results
> are persisted to Postgres (`eval_runs` + `eval_result_cases`, migration 0003)
> and served read-only by Go `EvalService` (`RunEval` is intentionally
> `Unimplemented` — execution stays in the eval-runner / CI gate). The
> dashboard `/evals` and `/evals/[id]` pages are live. **Still pending:** the
> optional two-run comparison view (`/evals?compare=<a>&<b>`) and the CI
> eval-gate (`.github/workflows/eval-gate.yml`, Week 8). See
> [ADR-0006](../decisions/0006-custom-eval-runner.md).

**Location:** `apps/eval-runner/` (Python, uv). CI gate (planned) at `.github/workflows/eval-gate.yml`.

## Current state (2026-05-22)

`uv run harnessflow-eval --workflow-id <id> --dataset research-assistant` runs
the workflow over the dataset via the Connect HTTP API (no Temporal coupling),
scores each case, and prints a markdown (or JSON) report. Scorers:
`exact_match`, `embedding_similarity` (all-MiniLM cosine via ChromaDB, offline),
`llm_judge` (reuses the worker's `LLMClient` through a uv path dependency;
neutral 0.5 in mock mode). Latency p50/p95 and total cost come from each run's
metrics. The aggregate `overall_score` is what the deployment gate compares
against `requires_eval_pass.min_score`. Verified end-to-end against the live
research-assistant workflow.

**Responsibility:** Evaluate workflow quality, persist results, gate PRs that regress quality.

## Why we build this ourselves

Off-the-shelf eval frameworks (deepeval, ragas, langchain.evaluation) bury the design behind their abstractions. The eval framework is the single highest-signal recruiter differentiator in the project — outsourcing it hides the engineering. See [ADR-0006](../decisions/0006-custom-eval-runner.md).

`promptfoo` is integrated as an optional *consumer* (it can target a HarnessFlow workflow as a provider), but the runner is ours.

## Components

1. **Eval runner** (`harnessflow_eval/runner.py`) — loads a JSONL dataset, runs the target workflow N times per case via the Temporal client, applies configured scorers, persists results.
2. **Scorers** (`harnessflow_eval/scorers/`):
   - `exact_match.py` — for closed-set answers
   - `llm_judge.py` — Claude as judge, fixed rubric
   - `embedding_similarity.py` — cosine sim vs. ground truth (text-embedding-3-small)
   - `latency.py` — p50/p95 from `workflow_runs.duration_ms`
   - `cost.py` — sum of `workflow_steps.cost_usd_cents`
3. **Datasets** (`harnessflow_eval/datasets/`):
   - `research-assistant.jsonl` — 30 Q&A pairs with ground truth (week 7)
4. **Reporters** (`harnessflow_eval/reporters/`):
   - `markdown.py` — produces a markdown table for PR comments
   - `json.py` — for the dashboard
   - `pr_comment.py` — posts via `gh` CLI

## CI gate (week 8 — the killer recruiter feature)

`.github/workflows/eval-gate.yml`:

1. Trigger: any PR that modifies `packages/examples/workflows/*.yaml`.
2. Spin up docker-compose stack.
3. Run eval suite against both the PR version and `main` version of the workflow.
4. Diff the scores; produce markdown comparison.
5. Post comment on PR (via `gh pr comment`).
6. Set check status: green if all scorers within threshold, red if any regresses beyond `delta < min_delta` configured in the workflow YAML.

The week-14 autonomous mutation agent piggybacks on this exact same gate.

## Related ADRs

- [ADR-0006](../decisions/0006-custom-eval-runner.md) — custom eval runner

## TODO as we go

- [ ] Decide judge prompt for `llm_judge` — should match a known public benchmark style (HELM-lite?)
- [ ] Embedding model choice for similarity — `text-embedding-3-small` is cheap + good enough; lock it in via ADR if it changes
- [ ] Dataset versioning — do we version datasets alongside workflows? Probably yes (`datasets/research-assistant-v1.jsonl`)
- [ ] How many seeds per case? Start with N=3 to capture variance.
