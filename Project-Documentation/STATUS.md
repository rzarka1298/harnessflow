# STATUS

> **Read this first when resuming work.** Three sections only: DONE / IN FLIGHT / NEXT. Updated at the end of every working session.

_Last updated: 2026-05-19 (Week 1 Day 4–5)_

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
| 2026-05-19 | **Week 1 Day 4–5** — SDK contracts: proto files for WorkflowService/RunService/EvalService; workflow YAML JSON Schema + DSL SPEC.md. `make proto` wired (buf → Go/Python/TS, datamodel-codegen → Pydantic, go-jsonschema → Go structs); verified idempotent. Generated code committed; `go.work` joins the gen Go module. | _pending branch merge_ |

## IN FLIGHT

**Branch:** `feat/sdk-proto-schema` — about to commit + merge to `main`.

**Current task:** finishing Week 1 Day 4–5 — commit proto/schema/codegen, merge to `main`, push. **This completes Week 1.**

**Next file to touch:** `apps/api/migrations/0001_init.up.sql` — start of Week 2 (Postgres schema).

## NEXT (top 3 from ROADMAP)

1. **Week 2, Postgres schema**: Author migrations (`workflows`, `workflow_versions`, `workflow_runs`, `workflow_steps`), wire `sqlc` to generate type-safe queries into `apps/api/internal/store/`.
2. **Week 2, YAML→Temporal compiler**: `apps/api/internal/workflow/{parser,compiler}.go` — parse workflow YAML to an IR, compile to a Temporal workflow function.
3. **Week 2, Connect services**: implement `WorkflowService` + `RunService` handlers in `apps/api/internal/server/`, backed by Postgres + Temporal client.

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
