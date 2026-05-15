# STATUS

> **Read this first when resuming work.** Three sections only: DONE / IN FLIGHT / NEXT. Updated at the end of every working session.

_Last updated: 2026-05-15_

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
| 2026-05-15 | **Week 1 Day 2** — monorepo skeleton: `apps/api` (Go, Chi, slog, /healthz+/readyz), `apps/worker` (Python/uv, Temporal+Pydantic+structlog deps, config), `apps/dashboard` (Next.js 16.2.6 App Router + Tailwind). All 3 build, run, lint, type-check clean. `.golangci.yml` added. | _pending branch merge_ |

## IN FLIGHT

**Branch:** `feat/api-monorepo-skeleton` — about to commit + merge to `main`.

**Current task:** finishing Week 1 Day 2 — commit the monorepo skeleton, merge to `main`, push.

**Next file to touch:** `docker-compose.yml` at repo root — start of Week 1 Day 3.

## NEXT (top 3 from ROADMAP)

1. **Week 1, Day 3**: Stand up `docker-compose.yml` with Postgres, Temporal (via `temporalio/auto-setup` image), Redis, OTel Collector, Jaeger, Prometheus, Grafana. Verify all UIs reachable on standard ports. Fill in the `make up`/`make down`/`make logs` targets.
2. **Week 1, Day 4–5**: Author the first proto files (`packages/sdk/proto/workflow/v1/workflow.proto`, `run/v1/run.proto`, `eval/v1/eval.proto`) and the JSON Schema for workflow YAML (`packages/sdk/schema/workflow.schema.json`). Wire `make proto` to run Buf + datamodel-codegen and commit generated outputs to `packages/sdk/gen/`.
3. **Week 2**: Postgres schema (sqlc), YAML→Temporal compiler, Connect services. See ROADMAP.md Phase 1.

## Notes for next session

- Resume protocol: (1) `gh auth status`, (2) `export PATH="/opt/homebrew/bin:$PATH"` then confirm `go version` / `uv --version` / `pnpm --version`, (3) read `decisions/INDEX.md`, (4) begin Day 3.
- **Important env note:** Homebrew tools (go, terraform, helm, buf, sqlc, migrate, golangci-lint, gitleaks) live in `/opt/homebrew/bin` which is NOT on the default PATH in this shell — prefix commands with `export PATH="/opt/homebrew/bin:$PATH"`. `uv` is at `/opt/anaconda3/bin/uv`. `node`/`pnpm`/`npx` are on PATH via nvm.
- Run apps locally: API `cd apps/api && go run ./cmd/api`; worker `cd apps/worker && uv run harnessflow-worker`; dashboard `cd apps/dashboard && pnpm dev`.
- The `Makefile` targets are still stubs printing `TODO(week-N): ...` except `tools-check` (functional). They get filled in as code lands — `up`/`down`/`logs` next, in Day 3.
- Dashboard is Next.js **16.2.6** (newer than the "15" named in early docs). create-next-app added `apps/dashboard/AGENTS.md` warning that Next 16 has breaking changes vs training data — heed it when writing dashboard code in Week 4.
