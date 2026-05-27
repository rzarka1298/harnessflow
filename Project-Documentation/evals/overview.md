# Evals — Overview

> **Status (Week 8, complete).** Eval runner + persistence + dashboard pages +
> CI eval-gate are all in. `apps/eval-runner/` has three quality scorers,
> the `research-assistant.jsonl` dataset, the httpx-based runner,
> markdown/JSON reporters, a CLI with `--baseline-json`/`--out-{json,md}`
> /`--gate-max-regression` flags, and 10 unit tests (including 5 for the
> gate). Results persist to Postgres (`eval_runs` + `eval_result_cases`,
> migration 0003) and are served read-only by Go `EvalService`. Dashboard
> `/evals` + `/evals/[id]` are live. The CI gate
> (`.github/workflows/eval-gate.yml` + `scripts/ci-eval-gate.py`) boots the
> dev stack on each PR that touches a workflow YAML, registers
> baseline-vs-PR, evals both, posts the markdown diff as a PR comment, and
> fails the check on any per-scorer regression beyond `--gate-max-regression`
> (default 0.05). The week-14 autonomous mutation agent piggybacks on this
> exact gate. See [ADR-0006](../decisions/0006-custom-eval-runner.md).

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

## CI gate (week 8 — the killer recruiter feature, now live)

`.github/workflows/eval-gate.yml` + `scripts/ci-eval-gate.py`:

1. **Trigger:** any PR that modifies `packages/examples/workflows/*.yaml`
   (also re-runs on changes to the eval-runner or the gate scripts themselves
   so the gate is exercised end-to-end on its own PRs).
2. **Boot:** `docker compose up -d postgres redis temporal otel-collector`,
   apply Postgres migrations via `psql`, build the Go API + Python worker
   (host processes, `nohup`), seed the ChromaDB corpus, wait for `/readyz`.
3. **Diff inputs:** `git diff --name-only origin/<base>...HEAD --
   'packages/examples/workflows/*.yaml'` — files added on this PR.
4. **For each file** (in `scripts/ci-eval-gate.py`):
   - Read the baseline YAML via `git show origin/<base>:<path>` (skipped when
     a file is newly added — the PR run is reported ungated for visibility).
   - Rewrite `name:` in each copy with a per-role suffix
     (`-gate-{base,pr}-<8 hex>`) so the `(name, version)` UNIQUE constraint
     on `workflows` doesn't reject the second registration.
   - POST each to `WorkflowService.CreateWorkflow`, run the eval-runner
     against each; the PR run gets `--baseline-json <base.json>
     --gate-max-regression 0.05` so its markdown output includes a Δ column
     and its exit code reflects the gate verdict.
   - Files whose stem doesn't match any dataset under
     `apps/eval-runner/harnessflow_eval/datasets/` (e.g. `approval-demo.yaml`)
     are skipped with a logged note.
5. **Comment:** concatenated per-file markdown is posted via `gh pr comment
   --body-file`. New comment each PR push; sticky-comment upgrade is a
   later polish.
6. **Verdict:** the workflow fails if any file's gate exit code was nonzero.

The gate runs against MockProvider (no LLM keys in CI), so scores are
deterministic and free. The week-14 autonomous mutation agent piggybacks on
this exact gate.

The gate is testable locally: bring up `make up` + the api + worker, then
`make eval-gate` (which runs `scripts/ci-eval-gate.py` against whatever
YAMLs have changed vs `origin/main`).

## Related ADRs

- [ADR-0006](../decisions/0006-custom-eval-runner.md) — custom eval runner

## TODO as we go

- [ ] Decide judge prompt for `llm_judge` — should match a known public benchmark style (HELM-lite?)
- [ ] Embedding model choice for similarity — `text-embedding-3-small` is cheap + good enough; lock it in via ADR if it changes
- [ ] Dataset versioning — do we version datasets alongside workflows? Probably yes (`datasets/research-assistant-v1.jsonl`)
- [ ] How many seeds per case? Start with N=3 to capture variance.
