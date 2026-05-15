"""Worker entrypoint.

Week 1 skeleton: loads config and logs a startup banner. Temporal worker
registration and activity wiring land in Week 3 — see ROADMAP.md.
"""

from __future__ import annotations

import structlog

from harnessflow_worker import __version__
from harnessflow_worker.config import WorkerConfig

log = structlog.get_logger()


def main() -> None:
    """Start the HarnessFlow worker."""
    cfg = WorkerConfig.load()
    log.info(
        "starting harnessflow worker",
        version=__version__,
        temporal_host=cfg.temporal_host,
        temporal_namespace=cfg.temporal_namespace,
        task_queue=cfg.temporal_task_queue,
        environment=cfg.environment,
    )
    # Week 3: connect to Temporal, register activities, run the worker loop.
    log.info("worker skeleton ready — activity registration lands in Week 3")


if __name__ == "__main__":
    main()
