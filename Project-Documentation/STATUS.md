# STATUS

> **Read this first when resuming work.** Three sections only: DONE / IN FLIGHT / NEXT. Updated at the end of every working session.

_Last updated: 2026-05-22 (Week 7 in progress — eval runner core landed)_

## DONE

| Date | Item | Commit |
| --- | --- | --- |
| 2026-05-14 | Approved 14-week project plan written and saved to `~/.claude/plans/i-am-developing-a-serialized-codd.md` | (pre-repo) |
| 2026-05-14 | Repo scaffold: LICENSE, README, ARCHITECTURE, CLAUDE.md, Makefile, .gitignore, .env.example, .envrc.example | 92b178c |
| 2026-05-14 | Project-Documentation skeleton — all 10 subfolders, all overview stubs, README, STATUS, ROADMAP | 92b178c |
| 2026-05-14 | Pre-seeded ADRs 0001–0008 + INDEX.md | 92b178c |
| 2026-05-14 | Developer toolchain installed: go 1.26.3, terraform 1.15.3, helm 4.2.0, buf 1.69.0, sqlc 1.31.1, golang-migrate, golangci-lint, uv 0.6.3, gitleaks | (local env) |
| 2026-05-14 | Public GitHub repo created: https://github.com/rzarka1298/harnessflow | — |
| 2026-05-14 | First commit pushed to origin/main | 92b178c |
| 2026-05-15 | **Week 1 Day 2** — monorepo skeleton: `apps/api` (Go, Chi, slog, /healthz+/readyz), `apps/worker` (Python/uv, Temporal+Pydantic+structlog deps, config), `apps/dashboard` (Next.js 16.2.6 App Router + Tailwind). All 3 build, run, lint, type-check clean. `.golangci.yml` added. | ff022d2 |
| 2026-05-15 | **Week 1 Day 3** — docker-compose dev stack: postgres, redis, temporal, temporal-ui, otel-collector, jaeger, prometheus, grafana, minio. Observability configs + Grafana provisioning. Makefile up/down/logs/ps/restart/nuke. Verified: all UIs 200, Temporal SERVING, Prometheus targets up, OTLP span flows to Jaeger. | 35748c5 |
| 2026-05-19 | **Week 1 Day 4–5** — SDK contracts: proto files for WorkflowService/RunService/EvalService; workflow YAML JSON Schema + DSL SPEC.md. `make proto` wired (buf → Go/Python/TS, datamodel-codegen → Pydantic, go-jsonschema → Go structs); verified idempotent. Generated code committed; `go.work` joins the gen Go module. | 36365ef |
| 2026-05-19 | **Week 2, commit 1/3** — Postgres schema + sqlc + store: migrations 0001_init (workflows, workflow_runs, workflow_steps), sqlc.yaml + queries, pgx pool. Makefile `sqlc`/`migrate-up`/`migrate-down`/`migrate-status`. Migration applied. | (branch) |
| 2026-05-19 | **Week 2, commit 2/3** — YAML→Temporal compiler: `internal/workflow` parser (sigs.k8s.io/yaml + Kahn topo sort + cross-field validation), `HarnessFlowWorkflow` Temporal function, Week-2 stub activities (replaced by Python in Week 3), Temporal client + worker wiring. Parser unit tests pass; api boots and worker polls. | (branch) |
| 2026-05-19 | **Week 2, commit 3/3** — Connect handlers + OTel: WorkflowService + RunService backed by Postgres + Temporal; OTLP/gRPC tracer init; Connect + Temporal OTel interceptors. End-to-end demo verified: POST workflow → POST run → Temporal `COMPLETED` → 1+1 Postgres rows → **single 16-span Jaeger trace** spanning Connect RPC → Temporal client → workflow → each activity start+run. | d54280d |
| 2026-05-20 | **Week 3, commit 1/3** — In-house `LLMClient` (~300 LOC with provider classes; ~120 LOC routing brain) with OpenAI / Anthropic / Mock providers, YAML-declared fallback graph, OTel GenAI semconv spans, pinned price table, build_default_client env factory. 9 unit tests cover routing, fallback walk, cost accounting, mock determinism. | (branch) |
| 2026-05-20 | **Week 3, commit 2/3** — Python worker bootstrap: OTel SDK init (mirrors api side) + asyncpg pool + Pydantic types wire-compatible with Go ActivityInput/Result. Worker connects to Temporal with pydantic_data_converter + TracingInterceptor. | (branch) |
| 2026-05-20 | **Week 3, commit 3/3** — Real activities (`llm_call`, `retrieve` stub, `tool_call` stub, `verify` LLM-as-judge) + idempotent step persistence (UUIDv5-keyed); Go-side stub activities removed (Workflow stays in Go). End-to-end demo: single-LLM-step YAML → Temporal COMPLETED → workflow_steps row with tokens/cost → **8-span Jaeger trace spanning BOTH `harnessflow-api` and `harnessflow-worker`** — Connect RPC → StartWorkflow → RunWorkflow → StartActivity → RunActivity (Python) → llm.mock.complete. | 19e9924 |
| 2026-05-21 | **Week 4, commit 1/3** — Research-assistant YAML (planner→retriever→executor→verifier) + 20-doc ChromaDB corpus + real ChromaDB-backed `retrieve` activity. Fixed Go-side `LocalActivityWorkerOnly: true` so the api stops racing the python worker for activity tasks. | (branch) |
| 2026-05-21 | **Week 4, commit 2/3** — Dashboard MVP: `/workflows`, `/workflows/[id]` (React Flow DAG via dagre), `/runs`, `/runs/[id]` (steps + tokens/cost + Jaeger deep-link). Connect-Web client over the protobuf-es v2 service descriptors; TanStack Query with 2s polling on in-progress runs. CORS middleware on the api. `make proto` syncs `packages/sdk/gen/ts` → `apps/dashboard/src/gen` (Turbopack rejects symlinks outside the project root). | (branch) |
| 2026-05-21 | **Week 4, commit 3/3** — `scripts/demo.sh` + `make demo`. Verified: 4 steps complete with real ChromaDB retrieval (retriever ~260ms), browser-origin CORS preflight returns 204, dashboard build clean. **Tagged `v0.1.0-thin-slice`.** | b9953da |
| 2026-05-21 | **Week 5, commit 1/3** — Run-status completion path: `record_run_status` activity (running → completed/failed) + `update_run_status` (stamps started/ended, returns duration). Workflow brackets steps with status calls. `workflow_name` threaded into ActivityInput. Closes the Week-2 gap. Verified run row reaches `completed` with duration. | 06d19e9 |
| 2026-05-21 | **Week 5, commit 2/3** — Worker Prometheus metrics via OTel: `harnessflow_workflow_runs_total`, `_duration_seconds`, `_llm_tokens_total`, `_llm_cost_usd_total`. Verified worker → collector → Prometheus (runs=2, tokens=1528, duration_count=2). | a5d48a2 |
| 2026-05-21 | **Week 5, commit 3/3** — Grafana dashboard `infrastructure/grafana/dashboards/harnessflow.json` (6 panels) auto-provisioned; Prometheus datasource pinned UID. ADR-0005 marked implemented. | 60767b0 |
| 2026-05-22 | **Week 6, commit 1/3** — Human approval gates: `RunService.ApproveRun` RPC; workflow pauses a `requires_approval` step on the Temporal "approve" signal (run status `waiting_approval`); dashboard Approve button; `approval-demo.yaml`. Verified pause → ApproveRun 200 → resume → completed. | 1cabf04 |
| 2026-05-22 | **Week 6, commit 2/3** — Reproducible self-healing: `MockProvider` fault injection via `HARNESSFLOW_MOCK_FAIL_MODELS`; research-assistant with `gpt-4o` "down" falls over to `claude-sonnet-4-6` and still completes. 10 worker tests pass. | 31cebf5 |
| 2026-05-22 | **Week 6, commit 3/4** — Failure analysis: migration 0002 (`input_preview`/`output_preview`); worker persists rendered prompt + response; proto Step + dashboard expandable step detail (error/prompt/response). Verified previews returned by GetRun. | 7891c80 |
| 2026-05-22 | **Week 6, commit 4/4** — Project-Documentation sweep: refreshed evals/dashboard/infrastructure/demo overviews to match reality, added `workers/llm-client.md` + `orchestration/temporal-patterns.md`, fixed stale claims found in a docs-vs-code audit. | 7891c80 |
| 2026-05-22 | **Week 7, commit 1/?** — Eval runner core: `apps/eval-runner/` (uv) with `exact_match`/`embedding_similarity`/`llm_judge` scorers, `research-assistant.jsonl` (10 cases), httpx Connect-API runner, report aggregation + markdown/JSON reporters, CLI, 5 unit tests. Reuses worker `LLMClient` via uv path dep (+ added `py.typed` to worker). Verified live: 3 cases scored → markdown report (overall 0.188 in mock mode). | _pending branch merge_ |

## IN FLIGHT

**Branch:** `feat/week7-eval-runner` — 1 commit so far. Week 7 in progress.

**Current task:** merge commit 1; then build eval persistence + `/evals` page (commit 2) and the CI eval-gate (Week 8).

**Next file to touch:** `apps/api/migrations/0003_eval_results.up.sql` — eval results persistence.

## NEXT (top 3 from ROADMAP)

1. **Week 7, eval persistence + EvalService** — `eval_results` (+ `eval_result_cases`) migration; implement the `EvalService` handler (RunEval/GetEvalRun/ListEvalRuns) so eval runs are stored and queryable; have the eval-runner POST results (or the API drive eval runs).
2. **Week 7, `/evals` dashboard page** — list eval runs + a two-run comparison table.
3. **Week 8, CI eval-gate** — `.github/workflows/eval-gate.yml`: on a PR that changes `packages/examples/workflows/*.yaml`, run the suite vs main, post the markdown comparison, block on regression. The `render_markdown(report, baseline)` diff path already exists.

## Releases

- `v0.1.0-thin-slice` — end-to-end research-assistant runs across Go API + Python worker + ChromaDB + dashboard, single OTel trace, all step rows persisted.

## Setting real LLM keys

Without keys the demo runs on `MockProvider` (deterministic, free). To swap in real models, create `.env` from `.env.example` and set `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY`, then re-run `make up` and the worker via `.venv/bin/python -m harnessflow_worker`.

## Dev stack quick reference (observability)

- Grafana `http://localhost:3000` → "HarnessFlow" dashboard (anonymous admin).
- Prometheus `http://localhost:9090`; metric names are `harnessflow_*` (see observability/overview.md).
- Worker metrics require the worker to be running and a few seconds to export (5s reader interval, 15s Prometheus scrape).

## Dev stack quick reference

- `make up` / `make down` / `make ps` / `make logs` / `make nuke` (deletes volumes).
- `make proto` regenerates all SDK clients; idempotent (CI enforces `git diff --exit-code`).
- UIs: Temporal `:8233`, Jaeger `:16686`, Prometheus `:9090`, Grafana `:3000`, MinIO `:9001`.
- OTLP ingest: gRPC `localhost:4317`, HTTP `localhost:4318`. Postgres `:5432`, Redis `:6379`, Temporal gRPC `:7233`.
- Credentials are all `harnessflow`/`harnessflow` (local dev only).
- **Go monorepo:** two modules (`apps/api`, `packages/sdk/gen/go`) joined by the repo-root `go.work`. Build with the workspace active.

## Dev stack quick reference

- `make up` / `make down` / `make ps` / `make logs` / `make nuke` (deletes volumes).
- UIs: Temporal `:8233`, Jaeger `:16686`, Prometheus `:9090`, Grafana `:3000`, MinIO `:9001`.
- OTLP ingest: gRPC `localhost:4317`, HTTP `localhost:4318`. Postgres `:5432`, Redis `:6379`, Temporal gRPC `:7233`.
- Credentials are all `harnessflow`/`harnessflow` (local dev only).

## Notes for next session

- Resume protocol: (1) `gh auth status`, (2) `export PATH="/opt/homebrew/bin:$PATH"` then confirm `go version` / `uv --version` / `pnpm --version`, (3) read `decisions/INDEX.md`, (4) begin Day 3.
- **Important env note:** Homebrew tools (go, terraform, helm, buf, sqlc, migrate, golangci-lint, gitleaks) live in `/opt/homebrew/bin` which is NOT on the default PATH in this shell — prefix commands with `export PATH="/opt/homebrew/bin:$PATH"`. `uv` is at `/opt/anaconda3/bin/uv`. `node`/`pnpm`/`npx` are on PATH via nvm.
- Run apps locally: API `cd apps/api && go run ./cmd/api`; worker `cd apps/worker && uv run harnessflow-worker`; dashboard `cd apps/dashboard && pnpm dev`.
- The `Makefile` targets are still stubs printing `TODO(week-N): ...` except `tools-check` (functional). They get filled in as code lands — `up`/`down`/`logs` next, in Day 3.
- Dashboard is Next.js **16.2.6** (newer than the "15" named in early docs). create-next-app added `apps/dashboard/AGENTS.md` warning that Next 16 has breaking changes vs training data — heed it when writing dashboard code in Week 4.
