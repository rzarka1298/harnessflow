"""Offline tests for the Parquet transform + partition key. No Kafka or S3
involved — the pure functions are deliberately separable from the I/O."""

from __future__ import annotations

import io
import re
from datetime import UTC, datetime

import pyarrow.parquet as pq

from harnessflow_events.consumer import _parse
from harnessflow_events.sink import SCHEMA, events_to_parquet, partition_key


def test_parquet_roundtrip_preserves_values() -> None:
    records = [
        {
            "event_id": "e1",
            "event_type": "run.completed",
            "occurred_at": "2026-05-28T00:00:00+00:00",
            "run_id": "r1",
            "workflow_name": "research-assistant",
            "status": "completed",
            "duration_s": 1.43,
        },
        {
            "event_id": "e2",
            "event_type": "step.completed",
            "run_id": "r1",
            "step_name": "planner",
            "step_type": "llm_call",
            "latency_ms": 820,
            "input_tokens": 10,
            "output_tokens": 20,
            "cost_usd_cents": 0,
        },
    ]
    table = pq.read_table(io.BytesIO(events_to_parquet(records)))
    assert table.num_rows == 2
    # Stable schema regardless of which event types are present in the batch.
    assert table.schema.names == SCHEMA.names
    rows = table.to_pylist()
    assert rows[0]["event_type"] == "run.completed"
    assert rows[0]["duration_s"] == 1.43
    # Columns not set on a run.* event stay null.
    assert rows[0]["step_name"] is None
    assert rows[1]["latency_ms"] == 820
    # Columns not set on a step.* event stay null.
    assert rows[1]["duration_s"] is None


def test_schema_stable_across_homogeneous_batches() -> None:
    # A batch of only run.* events must produce the same column set as a
    # batch with step.* events — the explicit schema guarantees this.
    only_runs = [{"event_id": "e", "event_type": "run.started", "run_id": "r"}]
    table = pq.read_table(io.BytesIO(events_to_parquet(only_runs)))
    assert table.schema.names == SCHEMA.names
    assert table.column("latency_ms").null_count == 1


def test_unknown_keys_dropped_missing_keys_nulled() -> None:
    records = [{"event_id": "e", "event_type": "run.started", "run_id": "r", "bogus": 1}]
    table = pq.read_table(io.BytesIO(events_to_parquet(records)))
    assert "bogus" not in table.schema.names
    assert table.to_pylist()[0]["workflow_name"] is None


def test_partition_key_is_hive_date_partitioned() -> None:
    key = partition_key("workflow-events", datetime(2026, 5, 28, 12, 0, tzinfo=UTC))
    assert re.fullmatch(r"workflow-events/dt=2026-05-28/\d+-[0-9a-f]{8}\.parquet", key)


def test_parse_skips_bad_payloads() -> None:
    assert _parse(b"not json") is None
    assert _parse(b"[1,2,3]") is None  # non-object
    assert _parse(b'{"event_type":"run.started"}') == {"event_type": "run.started"}
