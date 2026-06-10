"""CLI entrypoint for the event-firehose consumer.

    uv run harnessflow-event-consumer

Long-running: consumes the workflow-events topic and writes Parquet to S3
(MinIO locally). Exits cleanly on SIGINT/SIGTERM.
"""

from __future__ import annotations

import asyncio
import signal
from contextlib import suppress

import structlog

from harnessflow_events.config import ConsumerConfig
from harnessflow_events.consumer import EventConsumer
from harnessflow_events.sink import S3Sink

log = structlog.get_logger()


async def _amain() -> None:
    cfg = ConsumerConfig.load()
    sink = S3Sink(
        cfg.s3_bucket,
        cfg.s3_prefix,
        endpoint_url=cfg.s3_endpoint_url,
        region=cfg.s3_region,
        access_key=cfg.s3_access_key,
        secret_key=cfg.s3_secret_key,
    )
    # Convenient against a fresh MinIO; a no-op when the bucket already exists
    # (e.g. the Terraform-managed bucket on real S3).
    await asyncio.to_thread(sink.ensure_bucket)

    consumer = EventConsumer(cfg, sink)
    await consumer.start()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    run_task = asyncio.create_task(consumer.run())
    stop_task = asyncio.create_task(stop.wait())
    done, pending = await asyncio.wait({run_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
    if stop_task in done:
        log.info("shutdown signal received")
    await consumer.stop()
    for t in pending:
        t.cancel()
        with suppress(asyncio.CancelledError):
            await t
    log.info("event consumer stopped")


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
