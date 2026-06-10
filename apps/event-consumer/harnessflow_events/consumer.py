"""Consume loop: drain the workflow-events topic into Parquet batches on S3.

Delivery semantics are **at-least-once**: we write the Parquet object first,
then commit offsets. A crash between write and commit re-delivers the batch,
yielding a duplicate Parquet file — acceptable for an analytics sink (queries
dedupe on event_id), and strictly safer than commit-before-write (which would
silently drop events on a crash). Auto-commit is therefore disabled.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

from harnessflow_events.config import ConsumerConfig
from harnessflow_events.sink import S3Sink

log = structlog.get_logger()


class EventConsumer:
    def __init__(self, cfg: ConsumerConfig, sink: S3Sink) -> None:
        self._cfg = cfg
        self._sink = sink
        self._consumer: Any | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        from aiokafka import AIOKafkaConsumer

        self._consumer = AIOKafkaConsumer(
            self._cfg.topic,
            bootstrap_servers=self._cfg.brokers,
            group_id=self._cfg.group_id,
            enable_auto_commit=False,  # we commit only after a successful S3 write
            auto_offset_reset="earliest",
        )
        await self._consumer.start()
        log.info(
            "event consumer started",
            brokers=self._cfg.brokers,
            topic=self._cfg.topic,
            group=self._cfg.group_id,
        )

    async def stop(self) -> None:
        self._stopping.set()
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None

    async def run(self) -> None:
        """Poll → batch → flush loop. Flushes when the batch hits
        batch_max_events or batch_max_seconds elapses with pending records."""
        assert self._consumer is not None, "call start() first"
        batch: list[dict[str, Any]] = []
        poll_ms = max(250, int(self._cfg.batch_max_seconds * 1000))
        while not self._stopping.is_set():
            got = await self._consumer.getmany(timeout_ms=poll_ms)
            for _tp, msgs in got.items():
                for msg in msgs:
                    rec = _parse(msg.value)
                    if rec is not None:
                        batch.append(rec)
            # Flush on size, or on a non-empty batch after an idle poll window.
            if len(batch) >= self._cfg.batch_max_events or batch:
                await self._flush(batch)
                batch = []

    async def _flush(self, batch: list[dict[str, Any]]) -> None:
        if not batch:
            return
        assert self._consumer is not None
        # Write first, then commit — at-least-once (see module docstring).
        await asyncio.to_thread(self._sink.write, batch)
        await self._consumer.commit()


def _parse(raw: bytes) -> dict[str, Any] | None:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("skipping non-JSON message", size=len(raw))
        return None
    if not isinstance(obj, dict):
        log.warning("skipping non-object message")
        return None
    return obj
