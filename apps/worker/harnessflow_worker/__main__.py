"""Worker entrypoint.

Bring up OTel (must be first so the Temporal interceptor sees our provider),
then asyncpg, the LLM client, and finally the Temporal worker. Long-running:
exits on SIGINT/SIGTERM or an exception in the worker loop.

The activities that actually do work — llm_call, retrieve, tool_call, verify —
land in Week 3 commit 3. Until then we register only ``harnessflow_health`` so
the worker has something to anchor against.
"""

from __future__ import annotations

import asyncio
import signal
from contextlib import suppress

import structlog
from temporalio.client import Client
from temporalio.contrib.opentelemetry import TracingInterceptor
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from harnessflow_worker import __version__
from harnessflow_worker.activities.health import health
from harnessflow_worker.config import WorkerConfig
from harnessflow_worker.db import new_pool
from harnessflow_worker.llm import build_default_client
from harnessflow_worker.otel import setup_otel

log = structlog.get_logger()


async def _amain() -> None:
    cfg = WorkerConfig.load()
    log.info(
        "starting harnessflow worker",
        version=__version__,
        temporal_host=cfg.temporal_host,
        task_queue=cfg.temporal_task_queue,
        environment=cfg.environment,
    )

    tracer_provider = setup_otel(cfg.otlp_endpoint, "harnessflow-worker", cfg.environment)
    if tracer_provider:
        log.info("otel configured", endpoint=cfg.otlp_endpoint)

    pool = await new_pool(cfg.database_url)
    log.info("postgres connected")

    # The LLMClient is constructed once; activities reach for it via closure
    # when they land in commit 3.
    _llm = build_default_client()
    _ = _llm  # suppress unused-warning for now

    client = await Client.connect(
        cfg.temporal_host,
        namespace=cfg.temporal_namespace,
        data_converter=pydantic_data_converter,
    )
    log.info("temporal connected")

    worker = Worker(
        client,
        task_queue=cfg.temporal_task_queue,
        activities=[health],
        interceptors=[TracingInterceptor()],
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    log.info("worker started", task_queue=cfg.temporal_task_queue)
    worker_task = asyncio.create_task(worker.run())
    stop_task = asyncio.create_task(stop_event.wait())
    done, pending = await asyncio.wait(
        {worker_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
    )
    if stop_task in done:
        log.info("shutdown signal received")
    await worker.shutdown()
    for t in pending:
        t.cancel()
        with suppress(asyncio.CancelledError):
            await t

    await pool.close()
    if tracer_provider:
        tracer_provider.shutdown()
    log.info("worker stopped")


def main() -> None:
    """Synchronous entrypoint for the ``harnessflow-worker`` console script."""
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
