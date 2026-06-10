# ADR Index

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [0001](./0001-use-temporal-not-custom-orchestrator.md) | Use Temporal Go SDK, don't roll a custom orchestrator | Accepted | 2026-05-14 |
| [0002](./0002-connect-go-not-grpc.md) | Use Connect-Go over raw gRPC for the API surface | Accepted | 2026-05-14 |
| [0003](./0003-skip-langchain.md) | No LangChain — build a thin in-house LLMClient | Accepted | 2026-05-14 |
| [0004](./0004-skip-kafka-for-mvp.md) | Skip Kafka for MVP; use Temporal+Redis; add Redpanda in week 11 | Accepted (implemented Wk 11) | 2026-05-14 |
| [0005](./0005-otel-genai-semconv.md) | Adopt OpenTelemetry GenAI semantic conventions | Accepted | 2026-05-14 |
| [0006](./0006-custom-eval-runner.md) | Build a custom eval runner instead of using deepeval/ragas | Accepted | 2026-05-14 |
| [0007](./0007-contextual-bandit-not-deep-rl.md) | Use contextual bandits, not deep RL, for retry-policy learning | Proposed (week 13) | 2026-05-14 |
| [0008](./0008-autonomous-mutation-safety-model.md) | Autonomous workflow mutation safety model | Proposed (week 14) | 2026-05-14 |

## Conventions

- ADRs are written in [MADR-lite](https://adr.github.io/madr/) format: Context / Decision / Consequences / Alternatives considered.
- Status starts as `Proposed`. Flips to `Accepted` when the corresponding code lands on `main`. Becomes `Superseded by ADR-NNNN` if a later decision replaces it (never deleted).
- New ADR: copy the format, pick the next number, link from this INDEX, link the relevant subsystem `overview.md`.
- Pre-seeded ADRs 0001–0008 capture the major decisions baked into the approved plan; the corresponding features are built across weeks 1–14.
