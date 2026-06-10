# harnessflow-event-consumer

Drains the `harnessflow.workflow.events` Redpanda topic and writes the events
as date-partitioned Parquet to S3 (MinIO locally). The analytics tail of the
firehose described in [ADR-0004](../../Project-Documentation/decisions/0004-skip-kafka-for-mvp.md).

```
Redpanda topic ──► EventConsumer (poll+batch) ──► S3Sink ──► s3://<bucket>/workflow-events/dt=YYYY-MM-DD/<ts>-<id>.parquet
```

## Run locally

Requires the dev stack up (`make up`) — specifically Redpanda + MinIO — and a
worker emitting events (`HARNESSFLOW_EVENTS_BROKERS=localhost:19092`):

```bash
HARNESSFLOW_EVENTS_S3_ENDPOINT=http://localhost:9000 \
AWS_ACCESS_KEY_ID=harnessflow AWS_SECRET_ACCESS_KEY=harnessflow \
uv run --directory apps/event-consumer harnessflow-event-consumer
```

`make events-consume` wraps this. On real S3, drop the endpoint/keys (use
IRSA — see the Terraform `iam.tf`) and the same binary writes to the
Terraform-managed bucket.

## Design notes

- **At-least-once.** The consumer writes the Parquet object *then* commits
  offsets (auto-commit off). A crash in between re-delivers the batch — a
  duplicate Parquet file, which analytics dedupes on `event_id`. This is
  strictly safer than commit-before-write, which would drop events on a crash.
- **Fixed Arrow schema.** `sink.SCHEMA` pins the column set so a batch of only
  `run.*` events (all step columns null) produces the same Parquet schema as a
  batch with `step.*` events. Inference would not.
- **Decoupled from the producer.** The contract is the JSON on the topic, not
  a shared Python type. The consumer maps JSON dicts straight onto its Arrow
  schema; the producer's `WorkflowEvent` lives in the worker. Keeping them
  separate is the point of a firehose.
- **Batching** is bounded by `HARNESSFLOW_EVENTS_BATCH_MAX` (count) and
  `HARNESSFLOW_EVENTS_BATCH_SECONDS` (time), whichever trips first.

## Future steps

- Schema registry + Avro/Protobuf on the topic (today: JSON, validated by the
  fixed Arrow schema at write time).
- Compaction / a small batch-merge job — at high event rates the
  one-object-per-batch layout makes many small files.
