# ADR-0008: Autonomous workflow mutation safety model

Date: 2026-05-14
Status: Proposed (target: week 14)

## Context

The week-14 research extension is `apps/workflow-optimizer/` — a scheduled Python service that observes eval scores, asks Claude to propose a mutation to an underperforming workflow YAML, and applies the change. Autonomous code-writing agents carry real risks: scope creep into source code, surprising costs, hard-to-audit changes, security vulnerabilities introduced via prompt manipulation.

The job of this ADR is to define the safety model so the feature is impressive *because* it's contained — not in spite of being uncontained.

## Decision

The optimizer operates under the following hard constraints, all enforced in code (not policy):

1. **Mutation scope:** only files matching `packages/examples/workflows/*.yaml`. Source code, schemas, infra configs, and tests are off-limits. A path-prefix guard in the writer rejects anything else.
2. **Always opens a PR; never pushes directly.** Branch name is `optimizer/mutation-<short-hash>`. A human (or the eval gate) decides merge.
3. **Eval gate is the only auto-merge mechanism.** A separate GitHub Action with `mutation-approved` label auto-merges only if the existing week-8 eval gate is green AND scores strictly improve.
4. **Daily caps:** max 3 mutation PRs per 24h (counted via a `optimizer_runs` table); max $5 LLM spend per day (enforced by the LLMClient budget tracker).
5. **Structured output only.** Claude is invoked with Anthropic tool use; the schema is one of `{prompt_edit, model_swap, retry_policy_change, branch_threshold_change}`. No free-form code generation.
6. **Pre-PR smoke eval.** Before opening a PR, run a 5-case subset eval locally. If the mutation regresses the subset, abort without opening the PR.
7. **Audit trail.** Every mutation logs to `optimizer_runs` (input eval results, mutation type, Claude response, smoke-eval result, PR URL or abort reason). Inspectable in the dashboard.
8. **Killswitch.** Env var `OPTIMIZER_ENABLED=false` halts the scheduler immediately. Default is `false` until explicitly enabled.

## Consequences

- **Enables:** demonstrating a self-improving agent system that operates *safely* within a defined sandbox. The audit trail and PR history form the deliverable.
- **Forecloses:** mutating actual code (which would be more impressive but unsafe for a public OSS portfolio); skipping human review (which would be more autonomous but reckless).
- **Operational:** the scheduler is a Temporal cron workflow (eat-your-own-dogfood). The GitHub Actions integration uses the same `gh` CLI flow as the human contributor experience.
- **Recruiter signal:** This is a small, honest, *safely scoped* version of a research direction big AI labs care about (self-improving agent systems). Frame it that way — don't oversell as AGI, undersell as "scoped experiment."

## Alternatives considered

- **Allow source-code mutation.** Rejected: too risky for a public OSS repo; the demo signal isn't worth the security surface.
- **Auto-push to a `mutations/` branch instead of opening PRs.** Rejected: PR is the natural human-review surface; reusing the week-8 eval-gate Action means no new control plane.
- **No daily caps.** Rejected: a runaway agent could rack up $-cost or noise.
- **Use a smaller cheaper model (Haiku) for mutations.** Considered. Pinned to Sonnet 4.6 initially because mutation quality matters more than cost at scale of 3 PRs/day.
