"""Consumer configuration from the environment."""

from __future__ import annotations

import os

from pydantic import BaseModel


class ConsumerConfig(BaseModel):
    brokers: str
    topic: str
    group_id: str
    # Flush a Parquet object when either bound is hit.
    batch_max_events: int
    batch_max_seconds: float

    # S3 / MinIO sink.
    s3_bucket: str
    s3_prefix: str
    s3_endpoint_url: str | None
    s3_region: str
    s3_access_key: str | None
    s3_secret_key: str | None

    @classmethod
    def load(cls) -> ConsumerConfig:
        return cls(
            brokers=os.getenv("HARNESSFLOW_EVENTS_BROKERS", "localhost:19092"),
            topic=os.getenv("HARNESSFLOW_EVENTS_TOPIC", "harnessflow.workflow.events"),
            group_id=os.getenv("HARNESSFLOW_EVENTS_GROUP", "harnessflow-event-consumer"),
            batch_max_events=int(os.getenv("HARNESSFLOW_EVENTS_BATCH_MAX", "500")),
            batch_max_seconds=float(os.getenv("HARNESSFLOW_EVENTS_BATCH_SECONDS", "10")),
            s3_bucket=os.getenv("HARNESSFLOW_EVENTS_S3_BUCKET", "harnessflow-events"),
            s3_prefix=os.getenv("HARNESSFLOW_EVENTS_S3_PREFIX", "workflow-events"),
            # Empty endpoint => real AWS S3. Set to the MinIO URL locally.
            s3_endpoint_url=os.getenv("HARNESSFLOW_EVENTS_S3_ENDPOINT", "") or None,
            s3_region=os.getenv("AWS_REGION", "us-east-1"),
            s3_access_key=os.getenv("AWS_ACCESS_KEY_ID", "") or None,
            s3_secret_key=os.getenv("AWS_SECRET_ACCESS_KEY", "") or None,
        )
