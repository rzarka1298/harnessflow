# ADR-0006: Build a custom eval runner instead of using deepeval/ragas

Date: 2026-05-14
Status: Accepted

## Context

The eval framework is the project's highest-signal recruiter differentiator. We need scorers (exact match, LLM-as-judge, embedding similarity, latency, cost), a runner that drives workflows via the Temporal client, persistence to Postgres, comparison reports, and a CI gate.

Off-the-shelf options: `deepeval`, `ragas`, `langchain.evaluation`, `promptfoo`. All are opinionated about how datasets are structured, how scorers are configured, and how results are reported.

## Decision

**Build a custom eval runner (`apps/eval-runner/`, Python, ~600 lines).** Pure-functional scorers in `harnessflow_eval/scorers/`, a `Runner` class that loads a JSONL dataset and drives the workflow via the Temporal Python client, and reporters for markdown/JSON/PR-comment.

Integrate `promptfoo` as an optional *consumer* (it can target a HarnessFlow workflow as a provider via `harnessflow://workflows/<name>`), but the runner is ours.

## Consequences

- **Enables:** our datasets and scorers stay simple and inspectable. We can wire the eval results directly into the Connect API and dashboard without an adapter. The CI gate is a thin GitHub Action calling our runner — no third-party SaaS dependency.
- **Forecloses:** the prebuilt scorer libraries (e.g., ragas's RAG-specific metrics). Acceptable: we can reimplement the few that matter (faithfulness, context precision) in ~50 lines each.
- **Operational:** maintenance is on us. When a new scorer is needed, add a file in `scorers/` and a corresponding test.
- **Recruiter signal:** "I built our own eval framework because the off-the-shelf ones hid the design" is a strong, opinionated stance at AI-infra companies (Braintrust, Patronus, Helicone, Anthropic Frontier). The framework is itself the deliverable.

## Alternatives considered

- **`deepeval`.** Rejected: opinionated API; LLM-as-judge implementation locks us into their judge prompt structure.
- **`ragas`.** Rejected: RAG-specific; doesn't generalize to non-retrieval workflows.
- **`langchain.evaluation`.** Rejected by [ADR-0003](./0003-skip-langchain.md).
- **`promptfoo` as the runner.** Rejected as runner (we'd give up Temporal-client integration and Postgres persistence), accepted as an optional *consumer*.
