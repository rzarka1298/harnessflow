# CLAUDE.md — Briefing for AI coding agents

> **You are reading this because you (Claude) are picking up work on the HarnessFlow project. Read this file in full before doing anything else.**

## 1. What this project is

HarnessFlow is an open-source AI workflow orchestration + observability + CI/CD + evaluation platform for AI agents — "GitHub Actions + Temporal + Datadog for AI agents." Built as a **portfolio + learning project** by [rzarka1298](https://github.com/rzarka1298) over 14 weeks, full-time, to demonstrate AI-infra / platform-engineering depth to recruiters at AI-infra-leaning companies.

Two motivations, in priority order: (1) **learn** modern AI infra (Temporal, OTel, agent runtimes, eval systems, K8s); (2) **stand out** as a portfolio piece. Optimize accordingly — depth of understanding > shipping features fast.

## 2. Where the source of truth lives

| Question | File |
| --- | --- |
| "What's the current state of the project?" | `Project-Documentation/STATUS.md` — **read this FIRST every session** |
| "What's the plan?" | `Project-Documentation/ROADMAP.md` — the 14-week breakdown |
| "Why was X built this way?" | `Project-Documentation/decisions/INDEX.md` then the relevant ADR |
| "How does <subsystem> work?" | `Project-Documentation/<subsystem>/overview.md` |
| "How do I use HarnessFlow?" | `docs/` — public-facing docs |
| "What was the original spec?" | `Harness PRD.md` — aspirational; ROADMAP.md is the actual build plan |
| "Master plan with all rationale?" | `~/.claude/plans/i-am-developing-a-serialized-codd.md` (approved 14-week plan) |

## 3. Architecture in one paragraph

A Go orchestrator (`apps/api`, Connect-Go + Temporal Go SDK + sqlc) accepts workflow YAML, validates against JSON Schema, persists to Postgres, and compiles the YAML into deterministic Temporal Workflow functions. Python workers (`apps/worker`, Temporal Python SDK) register against the same Temporal cluster and run activities — `llm_call`, `retrieve`, `tool_call`, `verify` — that call OpenAI/Anthropic via a thin in-house `LLMClient` (no LangChain). Everything is instrumented with OpenTelemetry; trace context propagates Go → Temporal → Python → LLM-call as a single trace ID in Jaeger. A Next.js dashboard (`apps/dashboard`) consumes the same Connect services as a typed client via Connect-ES. Eval framework (`apps/eval-runner`) gates PRs that modify workflows; weeks 13–14 add a contextual-bandit retry policy learner and an autonomous YAML mutation agent.

## 4. Repo map

| Path | Tech | Owner-level |
| --- | --- | --- |
| `apps/api/` | Go | Orchestrator, Connect API, sqlc queries, migrations |
| `apps/worker/` | Python (uv) | Temporal activities, LLMClient, retrieval |
| `apps/dashboard/` | Next.js 15 TS | UI |
| `apps/eval-runner/` | Python (uv) | Eval framework |
| `apps/policy-learner/` | Python (uv) | Week-13: contextual bandit |
| `apps/workflow-optimizer/` | Python (uv) | Week-14: autonomous mutation |
| `packages/sdk/proto/` | proto | Source of truth for RPC types — all clients codegen from here |
| `packages/sdk/schema/` | JSON Schema | Source of truth for workflow YAML — Pydantic + Go structs codegen from here |
| `packages/examples/workflows/` | YAML | Canonical example workflows; the only thing `workflow-optimizer` is allowed to mutate |
| `infrastructure/terraform/` | HCL | AWS EKS env |
| `infrastructure/helm/harnessflow/` | Helm | Production K8s deployment |
| `infrastructure/{otel,prometheus,grafana}/` | yaml/json | Observability config |
| `docs/` | md | Public-facing docs |
| `Project-Documentation/` | md | **Internal dev journal — your home base** |
| `.github/workflows/` | yaml | CI: lint, tests, eval-gate, release |
| `scripts/` | bash/py | Dev scripts: seed-db, demo runner, recording |

## 5. Conventions

### Branches
- `main` is always demoable. `make up && make demo` works on `main` at every commit (or has a labeled "WIP — broken on `main`" issue open).
- Feature branches: `feat/<area>-<short-desc>` (e.g., `feat/api-yaml-compiler`).
- Research extensions (weeks 13–14) live on `research/v1.1` — they merge to `main` only if eval-gate passes.

### Commits
- **Conventional Commits** with area scope. Examples:
  - `feat(api): YAML→Temporal compiler skeleton`
  - `fix(worker): handle OpenAI 429 with exponential backoff`
  - `docs(decisions): add ADR-0007 contextual-bandit-not-deep-rl`
  - `chore: bump go.work toolchain to 1.23.4`
- One topic per commit. Don't batch a bug fix with a feature.

### Doc-as-you-go
- Every PR that changes behavior updates the relevant `Project-Documentation/<area>/<file>.md` in the same PR.
- If you make a non-trivial decision, write an ADR in the same PR (`Project-Documentation/decisions/NNNN-slug.md`).

### Checkpoint protocol — **MANDATORY**
1. At end of every working session: update `Project-Documentation/STATUS.md`.
2. Commit + push to `origin/main` (or the active feature branch).
3. End-of-feature: open a PR (or fast-forward if working solo on a feature branch), update `decisions/INDEX.md` if any ADRs were added.
4. Tag releases at milestones — see `ROADMAP.md` for the planned tags (`v0.1.0-thin-slice`, `v0.5.0-cicd`, `v1.0.0`, `v1.1.0-research`).

### Code style
- Go: `gofmt` + `golangci-lint`. Use `log/slog` for logs. No `panic()` in non-init code.
- Python: `ruff format` + `ruff check` + `mypy --strict`. Pydantic v2 for all I/O at boundaries.
- TS: `eslint` + `prettier`. Strict TS config.
- All files terminated with newline. No trailing whitespace. UTF-8.

### Generated code
- Buf and JSON-Schema codegen outputs ARE committed (in `packages/sdk/gen/`). A recruiter cloning the repo should never need to run codegen to read or run the project.
- CI enforces: `make proto && git diff --exit-code` must succeed.

## 6. How to resume a session (READ THIS IF YOU ARE A FRESH CLAUDE)

1. **Read `Project-Documentation/STATUS.md`.** That's the entire state — what's done (with commit SHAs), what's in flight (with current branch + exact next file + next step), and what's next.
2. **Read `Project-Documentation/decisions/INDEX.md`** for the list of accepted ADRs. If a decision seems unclear, open the relevant ADR.
3. **Open the in-flight area's `Project-Documentation/<area>/overview.md`.** Only that area. Do not read the entire repo.
4. **`git log --oneline -20`** to see recent activity.
5. Begin where the previous session left off. Update STATUS.md when you finish, commit, and push.

**You do NOT need to re-read the PRD or the full plan unless STATUS.md or an ADR indicates an architectural question is open.** They are stable docs.

## 7. What NOT to do

- **No LangChain.** Anywhere. See ADR-0003. The in-house `LLMClient` is ~200 lines and lives in `apps/worker/harnessflow_worker/llm/client.py`.
- **No Kafka before week 11.** See ADR-0004. Temporal is the queue. Redis is for ephemeral pub/sub.
- **No EKS deploy before week 12.** Terraform plans only from week 11.
- **No extending the YAML DSL without an ADR.** The DSL spec is in `packages/workflow-dsl/SPEC.md`; changes go through `Project-Documentation/decisions/`.
- **No batch commits** spanning multiple feature areas. One commit per topic.
- **No skipped pre-commit hooks** (`--no-verify`) — fix what fails, don't bypass.
- **No deploys to public infra** without explicit user OK in the conversation.
- **No mutations to non-YAML files by the `workflow-optimizer`** (week 14). It only opens PRs against `packages/examples/workflows/*.yaml`.
- **Do not introduce a feature flag system, telemetry pipeline, or auth layer** beyond what's spec'd. Single env-var API key for MVP; full RBAC is post-v1.

## 8. PRD pointer

`Harness PRD.md` (repo root) is the **aspirational** product requirements doc. It defines the long-term vision but is NOT the build plan — the build plan is `Project-Documentation/ROADMAP.md`. Any conflict between the two: the ROADMAP wins for current scope, the PRD wins for long-term direction.

## 9. Working with the user (rzarka1298)

- Prefers opinionated technical direction. Lead with a single recommendation, defend it briefly, do not enumerate options.
- Pushes back specifically when scope cuts go too far — surface cuts explicitly so he can override.
- Wants doc-as-you-go: never let documentation lag the code by more than a session.
- Wants frequent commits + pushes — at every checkpoint, no hoarding local work.
- Treats this as a *learning* project, not just a portfolio piece — when you make a non-obvious choice, write down *why* in the relevant doc or ADR. This is for the user's learning as much as for future Claude.
