# STATUS

> **Read this first when resuming work.** Three sections only: DONE / IN FLIGHT / NEXT. Updated at the end of every working session.

_Last updated: 2026-05-14_

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

## IN FLIGHT

**Branch:** none — `main` is at 92b178c, fully synced with `origin/main`. Ready to branch.

**Current task:** none in flight. Day 1 of Week 1 complete.

**Next file to touch:** `apps/api/go.mod` — create on a new `feat/api-monorepo-skeleton` branch as the start of Week 1, Day 2.

## NEXT (top 3 from ROADMAP)

1. **Week 1, Day 2**: Initialize the monorepo workspace — `apps/api/go.mod`, `apps/worker/pyproject.toml` (via `uv init`), `apps/dashboard/package.json` (via `pnpm create next-app`). Get a hello-world from all three. `make help` should list the targets.
2. **Week 1, Day 3**: Stand up `docker-compose.yml` with Postgres, Temporal (via `temporalio/auto-setup` image), Redis, OTel Collector, Jaeger, Prometheus, Grafana. Verify all UIs reachable on standard ports.
3. **Week 1, Day 4–5**: Author the first proto files (`packages/sdk/proto/workflow/v1/workflow.proto`, `run/v1/run.proto`, `eval/v1/eval.proto`) and the JSON Schema for workflow YAML (`packages/sdk/schema/workflow.schema.json`). Wire `make proto` to run Buf + datamodel-codegen and commit generated outputs to `packages/sdk/gen/`.

## Notes for next session

- After this scaffold lands, the next Claude session should: (1) verify `gh auth status` is still good, (2) confirm Go is on PATH (`go version`), (3) read `Project-Documentation/decisions/INDEX.md` for ADR list, (4) begin Day 2 work.
- The `Makefile` targets are all stubs printing `TODO(week-N): ...`. They get filled in as the corresponding code lands.
