"""Workflow lifecycle event firehose — producer side.

The worker emits run- and step-level lifecycle events to a single Redpanda
(Kafka-API) topic, ``harnessflow.workflow.events``. A separate consumer
(apps/event-consumer) batches them into Parquet on S3 for analytics. See
ADR-0004 for why Redpanda, and why this is an *analytics* path rather than
the source of truth.

Design choices worth remembering:

* **Best-effort, never fatal.** ``emit`` swallows and logs any producer
  error. Postgres (written synchronously in the same activities) is the
  source of truth; the firehose is a lossy-tolerant analytics stream, so a
  Redpanda outage must never fail a workflow. This is at-least-once at best
  and we don't pretend otherwise.
* **Keyed by run_id.** All events for a run share a partition, so per-run
  ordering is preserved without a global order guarantee.
* **JSON on the wire.** One topic, both ends in-repo — a schema registry +
  Avro would be ceremony we don't need yet (noted as a future step in the
  event-consumer README).
* **Optional.** With no brokers configured the factory returns a NullEmitter
  and the worker runs exactly as before (so ``make demo`` needs no Redpanda).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

import structlog
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from aiokafka import AIOKafkaProducer

log = structlog.get_logger()

TOPIC_DEFAULT = "harnessflow.workflow.events"

# Event-type constants — kept as plain strings so the consumer's Parquet
# partition values are stable and greppable.
RUN_STARTED = "run.started"
RUN_COMPLETED = "run.completed"
RUN_FAILED = "run.failed"
STEP_COMPLETED = "step.completed"
STEP_FAILED = "step.failed"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class WorkflowEvent(BaseModel):
    """One lifecycle event. A single flat schema (nullable run/step fields)
    keeps the topic to one type and the downstream Parquet columnar-friendly;
    consumers filter on ``event_type``."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    occurred_at: str = Field(default_factory=_now_iso)

    run_id: str
    workflow_name: str = ""
    workflow_version: int | None = None

    # run.* fields
    status: str | None = None
    duration_s: float | None = None
    error: str | None = None

    # step.* fields
    step_name: str | None = None
    step_type: str | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd_cents: int | None = None

    def to_bytes(self) -> bytes:
        return self.model_dump_json().encode("utf-8")


class EventEmitter(Protocol):
    """What the activities depend on. Two implementations: Kafka + Null."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def emit(self, event: WorkflowEvent) -> None: ...


class NullEmitter:
    """No-op emitter used when no brokers are configured. Keeps the worker's
    behavior identical to pre-firehose when events are off."""

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def emit(self, event: WorkflowEvent) -> None:
        return None


class KafkaEventEmitter:
    """aiokafka-backed emitter. ``aiokafka`` is imported lazily so the worker
    only requires it when events are actually enabled."""

    def __init__(self, brokers: str, topic: str = TOPIC_DEFAULT) -> None:
        self._brokers = brokers
        self._topic = topic
        # Duck-typed at runtime (tests inject a fake); aiokafka is imported
        # lazily in start() so the dep is only needed when events are enabled.
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        from aiokafka import AIOKafkaProducer

        producer = AIOKafkaProducer(
            bootstrap_servers=self._brokers,
            # Topic is auto-created by Redpanda in dev; enable_idempotence
            # keeps producer retries from duplicating within a session.
            enable_idempotence=True,
            acks="all",
            linger_ms=50,
        )
        await producer.start()
        self._producer = producer
        log.info("event emitter started", brokers=self._brokers, topic=self._topic)

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def emit(self, event: WorkflowEvent) -> None:
        if self._producer is None:
            return
        try:
            await self._producer.send_and_wait(
                self._topic,
                value=event.to_bytes(),
                key=event.run_id.encode("utf-8"),
            )
        except Exception as e:
            # Best-effort: never fail a workflow because the firehose is down.
            log.warning(
                "event emit failed (dropping)",
                event_type=event.event_type,
                run_id=event.run_id,
                error=str(e),
            )


def build_emitter(brokers: str, topic: str = TOPIC_DEFAULT) -> EventEmitter:
    """Return a KafkaEventEmitter when brokers are configured, else a
    NullEmitter. The returned emitter is not yet started."""
    if brokers.strip():
        return KafkaEventEmitter(brokers, topic)
    return NullEmitter()
