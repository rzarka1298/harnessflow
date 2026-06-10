# ADR-0004: Skip Kafka for MVP; use Temporal+Redis; add Redpanda in week 11

Date: 2026-05-14
Status: Accepted — **implemented Week 11 (2026-06-10)**

## Context

The PRD calls out Kafka as a core component for event-driven architecture. For a solo developer over 12 weeks, the operational weight of Kafka (Zookeeper/KRaft, schema registry, partitioning, consumer groups, monitoring) is enormous relative to what it buys.

Meanwhile, Temporal *is* a durable queue — workflow signals, activity task queues, and child-workflow dispatch are all event-driven primitives. Redis handles ephemeral pub/sub for the live dashboard and rate limiting.

The actual job Kafka would do — *event firehose for downstream analytics consumers* — is real but is not on the critical path for the demo workflow.

## Decision

**For the MVP (weeks 1–10): no Kafka.**
- Temporal task queues and signals do the durable-event work.
- Redis Streams for ephemeral dashboard live updates and rate limits.

**For week 11 (production polish): add Redpanda** (single-binary KRaft-mode Kafka, much lighter ops than vanilla Apache Kafka). One topic: `harnessflow.workflow.events`. One Python consumer that writes events as Parquet to S3 for analytics. This is a stretch goal — drop it if week 11 is tight.

## Consequences

- **Enables:** ship the demo with fewer moving parts. Avoid the Kafka rabbit hole that would consume 1–2 weeks if attempted from week 1.
- **Forecloses (temporarily):** event-stream fanout to arbitrary downstream consumers. Acceptable for MVP.
- **Operational:** docker-compose stays manageable. EKS doesn't need MSK provisioning.
- **Recruiter signal:** "I chose Temporal as the queue and added Redpanda as an analytics path, after defending the choice" reads as senior judgment. "I bolted on Kafka because everyone does" reads as cargo-culting.

## Implementation (Week 11)

Landed as designed — the stretch goal was not dropped.

- **Substrate:** single-binary Redpanda (KRaft dev mode) in docker-compose;
  on AWS the same topic would live on a managed broker. One topic,
  `harnessflow.workflow.events`.
- **Producer:** the worker emits run/step lifecycle events
  (`harnessflow_worker/events.py`), best-effort and optional — a Redpanda
  outage never fails a workflow, because Postgres is the source of truth and
  this is explicitly an analytics path, exactly as argued above. With no
  brokers configured the producer is a no-op (`NullEmitter`).
- **Consumer:** `apps/event-consumer/` drains the topic to date-partitioned
  Parquet on S3 (MinIO locally, Terraform-managed bucket + IRSA on EKS),
  at-least-once (write-then-commit).
- **Schema:** JSON on the wire, fixed Arrow schema at the Parquet boundary.
  A schema registry + Avro is noted as a future step, not built — it would be
  ceremony for one topic with both ends in-repo.

Verified end-to-end: a research-assistant run produced 6 events that the
consumer wrote to one Parquet object, read back valid. See
`Project-Documentation/infrastructure/overview.md` and the two app overviews.

## Alternatives considered

- **Apache Kafka from day 1.** Rejected: ops weight; no critical-path job.
- **NATS / NATS JetStream.** Rejected: another piece of infra to learn; doesn't add a recruiter bullet over Redpanda.
- **RabbitMQ.** Rejected: dated; weaker signal.
- **Skip Kafka entirely (no week 11 addition).** Rejected: missing the Kafka-class bullet is a real cost; Redpanda is the cheap way to get it.
