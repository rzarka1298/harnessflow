# ROADMAP

## Active direction — local PRD-to-verified-branch harness

The October 2026 approved product plan supersedes the schedule below. The PRD
coding harness is the primary product; the YAML workflow platform remains a
maintained foundation and demo. See [ADR-0009](decisions/0009-prd-project-runs.md),
[ADR-0010](decisions/0010-project-judge-and-cli.md), the active
[phase roadmap](../.planning/ROADMAP.md), and [STATUS](STATUS.md).

The release bar is a usable local launcher, durable project runs, isolated Codex
execution, independent command-based acceptance and review, explicit controls and
limits, a working project dashboard and CLI, repo-local Codex/Claude Code skills,
and real new/existing repository demonstrations. An explicit independent judge uses
Anthropic when configured and read-only Codex otherwise; frozen deterministic
acceptance commands remain required. AWS deployment, tenancy, additional coding
providers and research extensions are deferred.

The CLI, local skills and provider-aware judge are the current follow-up milestone.
The CLI and Codex judge fallback passed end-to-end trials; the Anthropic path awaits
a credentialed live call. See [STATUS](STATUS.md). When Anthropic is configured, the judge receives the PRD, diff,
plan and verification evidence, which are therefore sent to that external provider.

## Historical plan — 14 weeks to v1.1.0

> Preserved for architectural history. This schedule is not the current execution plan.

**Iron rules:**
1. Every Friday `docker compose up && make demo` succeeds.
2. v1.0 ships at the end of week 12 regardless of week 13–14 state.
3. Weeks 13–14 live on the `research/v1.1` branch — they merge only if the eval gate passes.

## Phase 0 — Foundation (Week 1)

Set up the monorepo, dev stack, codegen pipeline. Nothing runs yet, but `make up` and `make proto` both work and produce no diff.

- Repo skeleton, LICENSE, README, CLAUDE.md, Project-Documentation
- `apps/api` (Go), `apps/worker` (Python uv), `apps/dashboard` (Next.js) — all "hello world"
- `docker-compose.yml` — Postgres, Temporal, Redis, OTel Collector, Jaeger, Prometheus, Grafana
- `packages/sdk/proto/`, `packages/sdk/schema/`, Buf codegen wired, generated code committed

**Demo (Fri):** Connect server returns `ListWorkflows([])`; all UIs reachable.

## Phase 1 — Orchestration spine (Weeks 2–3)

Build the YAML→Temporal compiler and the Python worker. End-to-end: a YAML with one real LLM step actually runs.

### Week 2 — Go orchestrator
- Postgres schema + sqlc-generated queries + golang-migrate migrations
- YAML parser → IR → Temporal `Workflow` function
- Connect services: `WorkflowService.{Create,Get,List,Run}`, `RunService.{Get,List}`
- ADRs 0001, 0002 finalized

**Demo (Fri):** `POST /workflows` ingests a YAML; `POST /workflows/:id/run` starts a Temporal workflow with 3 stub activities (`sleep + log`); rows in Postgres; trace in Jaeger.

### Week 3 — Python workers + LLMClient
- Python worker registers against Temporal
- Activity types: `llm_call`, `retrieve`, `tool_call`, `verify`
- `LLMClient` (~200 lines): OpenAI + Anthropic, retries, OTel GenAI spans, $/token accounting
- ADR 0003 finalized

**Demo (Fri):** Single-LLM-step workflow runs end-to-end. Cost/tokens in Postgres. Full trace `api → temporal → activity → openai` in Jaeger.

## Phase 2 — Thin-slice MVP (Week 4) — `v0.1.0-thin-slice`

The research-assistant workflow runs end-to-end through every layer.

- Research-assistant demo workflow: `planner → retriever → executor → verifier`
- ChromaDB seeded with ~50 docs (Anthropic / Temporal / OTel content)
- Next.js dashboard: `/workflows`, `/workflows/[id]`, `/runs/[id]`
- React Flow DAG render from parsed YAML
- Tag `v0.1.0-thin-slice`. Record 2-min Loom.

## Phase 3 — Deepen the platform (Weeks 5–9)

Each week takes one layer from "minimally functional" to "demo-grade."

### Week 5 — Observability
- Full OTel everywhere; verify single-trace propagation Go ↔ Temporal ↔ Python
- Prometheus metrics: `harnessflow_workflow_runs_total`, `_duration_seconds`, `_llm_tokens_total`, `_llm_cost_usd_total`
- Grafana dashboard committed to `infrastructure/grafana/dashboards/harnessflow.json`
- Dashboard: live run polling, per-step token/cost/latency, deep links to Jaeger
- ADR 0005 finalized

### Week 6 — Self-healing + approval gates
- Per-step retry policy in YAML → Temporal `RetryPolicy`
- Declarative model-fallback graph (OpenAI primary → Anthropic on rate-limit)
- Approval gates via Temporal Signals
- Failure analysis page in dashboard

### Week 7 — Eval framework
- Eval runner: load dataset → run N times via Temporal client → score
- Scorers: exact match, LLM-as-judge, embedding similarity, latency p50/p95, cost
- 30-case dataset for the research-assistant workflow
- Dashboard `/evals` with comparison tables
- ADR 0006 finalized

### Week 8 — CI/CD eval-gate — `v0.5.0-cicd`
- GitHub Action: PR modifies workflow YAML → action runs eval suite vs main → markdown comparison comment → blocks merge if regression
- "Deployment gate" YAML clause: `deployment.requires_eval_pass: { min_score: 0.85 }`
- Self-PR with intentionally regressed prompt; capture screenshot of gate blocking
- Tag `v0.5.0-cicd`

### Week 9 — Dashboard polish
- Run Replay timeline (scrub through completed runs, see prompt/response per step)
- Animated DAG during in-progress runs
- Cost analytics page
- shadcn/ui polish: dark mode, empty states, error states

## Phase 4 — Production infra (Weeks 10–11)

### Week 10 — Helm + kind
- Helm chart with upstream subcharts (Postgres, Temporal, Redis, Jaeger, Prom, Grafana)
- Custom Deployments/Services for `api`, `worker`, `dashboard`, `eval-runner`
- HPA keyed on Temporal task-queue depth (custom metric)
- Test on local kind cluster

### Week 11 — Terraform + Redpanda
- Terraform: VPC, EKS (one node group, t3.medium), RDS Postgres, ElastiCache Redis, IAM/IRSA, S3
- Use `terraform-aws-modules/eks` + `vpc`
- `terraform plan` only — no apply yet
- Redpanda event firehose: workflow lifecycle events → Kafka topic → Python consumer → Parquet on S3
- ADR 0004 finalized

## Phase 5 — Ship v1.0 (Week 12)

- Mon: `terraform apply`, Helm install on EKS, smoke test
- Tue: record 5-min demo video
- Wed: polish README, ARCHITECTURE diagram (Excalidraw), quickstart works on fresh machine in <5 min
- Thu: 3 blog posts (trace correlation, eval gates, "why I didn't use LangChain")
- Fri: HN Show submission. Tag `v1.0.0`. `terraform destroy`.

## Phase 6 — Research extensions (Weeks 13–14, `research/v1.1` branch)

### Week 13 — Contextual-bandit retry policy learner
- `apps/policy-learner/` Python service
- Per-(workflow, step) Thompson-sampling models trained on Postgres run history
- New Connect endpoint `RetryPolicyService.Recommend`
- Worker queries policy on activity failure; uses dynamic retry params
- New YAML field: `retry_policy: { type: learned | static, fallback_to_static: bool }`
- A/B demo: same eval set, learned retries beat static on cost or latency
- ADR 0007 finalized

### Week 14 — Autonomous workflow mutation — `v1.1.0-research`
- `apps/workflow-optimizer/` Python service, scheduled via Temporal cron
- Loop: pull eval results → identify lagging workflow → ask Claude for structured mutation → apply to YAML copy → quick local eval → open PR via `gh`
- Existing week-8 eval-gate decides PR merge
- Safety rails: PR-only, daily PR cap, daily $ cap, structured-output schema, only mutates `packages/examples/workflows/*.yaml`
- ADR 0008 finalized
- Tag `v1.1.0-research`

## Verification (end of week 12 — all must pass on a fresh clone)

1. `make up` brings full stack up in <3 min, healthy
2. `make demo` runs research-assistant end-to-end
3. `/runs/<id>` in dashboard renders DAG + token/cost/latency + Jaeger link
4. Jaeger shows single trace across all layers with `gen_ai.*` attributes
5. Grafana dashboard shows the run's metrics
6. `make eval` runs the suite; results visible at `/evals`
7. Regression PR is blocked by the eval gate
8. `helm install harnessflow` on kind works
9. (Week 12 only) EKS deploy via Terraform + Helm works
10. `make demo-record` produces a Loom-ready terminal recording
11. (Week 13) `make demo-bandit` produces A/B graph
12. (Week 14) Git history contains a merged PR authored by `workflow-optimizer`
