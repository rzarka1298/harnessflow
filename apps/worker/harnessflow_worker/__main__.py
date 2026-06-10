"""Worker entrypoint.

Bring up OTel (must be first so the Temporal interceptor sees our provider),
then asyncpg, the LLM client, and finally the Temporal worker. Long-running:
exits on SIGINT/SIGTERM or an exception in the worker loop.

Registers the four DSL activities (``llm_call``, ``retrieve``, ``tool_call``,
``verify``) under their stable names. The Go workflow dispatches by name so the
worker that runs activities is invisible to it.
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
from harnessflow_worker.activities._common import Deps
from harnessflow_worker.activities.llm_call import make_llm_call
from harnessflow_worker.activities.record_run_status import make_record_run_status
from harnessflow_worker.activities.retrieve import make_retrieve
from harnessflow_worker.activities.tool_call import make_tool_call
from harnessflow_worker.activities.verify import make_verify
from harnessflow_worker.config import WorkerConfig
from harnessflow_worker.db import new_pool
from harnessflow_worker.events import build_emitter
from harnessflow_worker.llm import build_default_client
from harnessflow_worker.metrics import setup_metrics
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
    meter_provider = setup_metrics(cfg.otlp_endpoint, "harnessflow-worker", cfg.environment)
    if tracer_provider:
        log.info("otel configured", endpoint=cfg.otlp_endpoint)

    pool = await new_pool(cfg.database_url)
    log.info("postgres connected")

    llm = build_default_client()
    events = build_emitter(cfg.events_brokers, cfg.events_topic)
    await events.start()
    deps = Deps(pool=pool, llm=llm, events=events)

    client = await Client.connect(
        cfg.temporal_host,
        namespace=cfg.temporal_namespace,
        data_converter=pydantic_data_converter,
    )
    log.info("temporal connected")

    worker = Worker(
        client,
        task_queue=cfg.temporal_task_queue,
        activities=[
            make_llm_call(deps),
            make_retrieve(deps),
            make_tool_call(deps),
            make_verify(deps),
            make_record_run_status(deps),
        ],
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

    await events.stop()
    await pool.close()
    if tracer_provider:
        # force_flush BEFORE shutdown so in-flight spans reach the collector
        # even when the activity that produced them was the last thing to run.
        tracer_provider.force_flush(timeout_millis=5000)
        tracer_provider.shutdown()
    if meter_provider:
        # Same rationale for metrics: a short demo run finishes well within the
        # 5s export interval, so flush explicitly or the data never ships.
        meter_provider.force_flush(timeout_millis=5000)
        meter_provider.shutdown()
    log.info("worker stopped")


def main() -> None:
    """Synchronous entrypoint for the ``harnessflow-worker`` console script."""
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
