"""Unit tests for the workflow-event firehose producer side. No Kafka is
involved — we exercise the event model, the NullEmitter, the factory, and
the best-effort emit contract with a fake producer.
"""

from __future__ import annotations

import json

import pytest

from harnessflow_worker.events import (
    RUN_COMPLETED,
    KafkaEventEmitter,
    NullEmitter,
    WorkflowEvent,
    build_emitter,
)


def test_event_serializes_to_json_bytes() -> None:
    ev = WorkflowEvent(
        event_type=RUN_COMPLETED,
        run_id="r1",
        workflow_name="research-assistant",
        status="completed",
        duration_s=1.25,
    )
    payload = json.loads(ev.to_bytes())
    assert payload["event_type"] == "run.completed"
    assert payload["run_id"] == "r1"
    assert payload["duration_s"] == 1.25
    # auto-populated fields
    assert payload["event_id"]
    assert payload["occurred_at"]
    # unset step fields stay null (single flat schema)
    assert payload["step_name"] is None


def test_event_id_and_time_are_unique_per_instance() -> None:
    a = WorkflowEvent(event_type=RUN_COMPLETED, run_id="r")
    b = WorkflowEvent(event_type=RUN_COMPLETED, run_id="r")
    assert a.event_id != b.event_id


def test_build_emitter_returns_null_when_no_brokers() -> None:
    assert isinstance(build_emitter(""), NullEmitter)
    assert isinstance(build_emitter("   "), NullEmitter)


def test_build_emitter_returns_kafka_when_brokers_set() -> None:
    em = build_emitter("localhost:19092", "t")
    assert isinstance(em, KafkaEventEmitter)


@pytest.mark.asyncio
async def test_null_emitter_is_noop() -> None:
    em = NullEmitter()
    await em.start()
    await em.emit(WorkflowEvent(event_type=RUN_COMPLETED, run_id="r"))
    await em.stop()  # must not raise


@pytest.mark.asyncio
async def test_kafka_emit_is_best_effort_on_producer_error() -> None:
    """A producer failure must be swallowed — the firehose never fails a
    workflow."""

    class _BoomProducer:
        async def send_and_wait(self, *a: object, **k: object) -> None:
            raise RuntimeError("broker down")

    em = KafkaEventEmitter("localhost:19092", "t")
    em._producer = _BoomProducer()  # type: ignore[assignment]
    # Should not raise despite the producer blowing up.
    await em.emit(WorkflowEvent(event_type=RUN_COMPLETED, run_id="r"))


@pytest.mark.asyncio
async def test_kafka_emit_noop_before_start() -> None:
    em = KafkaEventEmitter("localhost:19092", "t")
    # No producer yet (start() not called) — emit is a no-op, not a crash.
    await em.emit(WorkflowEvent(event_type=RUN_COMPLETED, run_id="r"))
