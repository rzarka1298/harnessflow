"""Worker configuration loaded from the environment."""

from __future__ import annotations

import os

from pydantic import BaseModel


class WorkerConfig(BaseModel):
    """Runtime configuration for the HarnessFlow worker."""

    temporal_host: str
    temporal_namespace: str
    temporal_task_queue: str
    environment: str
    database_url: str
    otlp_endpoint: str
    # Redpanda/Kafka firehose. Empty brokers => events disabled (NullEmitter),
    # so the worker runs unchanged when Redpanda isn't present.
    events_brokers: str
    events_topic: str

    @classmethod
    def load(cls) -> WorkerConfig:
        """Build a config from environment variables, applying defaults."""
        return cls(
            temporal_host=os.getenv("TEMPORAL_HOST", "localhost:7233"),
            temporal_namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
            temporal_task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "harnessflow-tasks"),
            environment=os.getenv("ENVIRONMENT", "development"),
            database_url=os.getenv(
                "DATABASE_URL",
                "postgres://harnessflow:harnessflow@localhost:5432/harnessflow",
            ),
            # gRPC endpoint, no scheme. Empty disables tracing.
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT_GRPC", "localhost:4317"),
            events_brokers=os.getenv("HARNESSFLOW_EVENTS_BROKERS", ""),
            events_topic=os.getenv(
                "HARNESSFLOW_EVENTS_TOPIC", "harnessflow.workflow.events"
            ),
        )
