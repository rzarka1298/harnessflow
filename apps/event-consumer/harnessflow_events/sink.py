"""Parquet + S3 sink.

The pure transform (``events_to_parquet``) is separated from the S3 put so it
can be unit-tested offline. We pin an explicit Arrow schema rather than
inferring per-batch: events share one flat JSON shape with many nullable
columns, and inference on a batch that happens to contain only run.* events
(all step columns null) would otherwise produce a different schema than a
batch with step.* events — breaking downstream readers that expect a stable
column set.
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pyarrow as pa
import pyarrow.parquet as pq
import structlog

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

log = structlog.get_logger()

# Mirrors the producer's WorkflowEvent (apps/worker/harnessflow_worker/events.py).
# The contract between producer and consumer is the JSON on the topic; we keep
# the column list here so the two apps stay decoupled (a firehose, not a shared
# library). Order is the Parquet column order.
SCHEMA = pa.schema(
    [
        ("event_id", pa.string()),
        ("event_type", pa.string()),
        ("occurred_at", pa.string()),
        ("run_id", pa.string()),
        ("workflow_name", pa.string()),
        ("workflow_version", pa.int64()),
        ("status", pa.string()),
        ("duration_s", pa.float64()),
        ("error", pa.string()),
        ("step_name", pa.string()),
        ("step_type", pa.string()),
        ("latency_ms", pa.int64()),
        ("input_tokens", pa.int64()),
        ("output_tokens", pa.int64()),
        ("cost_usd_cents", pa.int64()),
    ]
)

_COLUMNS = [f.name for f in SCHEMA]


def events_to_parquet(records: list[dict[str, Any]]) -> bytes:
    """Serialize a batch of event dicts to Parquet bytes under the fixed
    SCHEMA. Missing keys become nulls; unknown keys are dropped."""
    columns: dict[str, list[Any]] = {name: [] for name in _COLUMNS}
    for rec in records:
        for name in _COLUMNS:
            columns[name].append(rec.get(name))
    table = pa.Table.from_pydict(columns, schema=SCHEMA)
    buf = io.BytesIO()
    # pyarrow.parquet ships incomplete types; write_table is untyped upstream.
    pq.write_table(table, buf, compression="snappy")  # type: ignore[no-untyped-call]
    return buf.getvalue()


def partition_key(prefix: str, now: datetime | None = None) -> str:
    """Hive-style date-partitioned object key:
    ``<prefix>/dt=YYYY-MM-DD/<epoch_ms>-<uuid8>.parquet``."""
    now = now or datetime.now(UTC)
    dt = now.strftime("%Y-%m-%d")
    fname = f"{int(now.timestamp() * 1000)}-{uuid.uuid4().hex[:8]}.parquet"
    return f"{prefix.rstrip('/')}/dt={dt}/{fname}"


class S3Sink:
    """Writes Parquet batches to S3. Targets MinIO locally via endpoint_url."""

    def __init__(
        self,
        bucket: str,
        prefix: str,
        *,
        endpoint_url: str | None,
        region: str,
        access_key: str | None,
        secret_key: str | None,
    ) -> None:
        import boto3

        self._bucket = bucket
        self._prefix = prefix
        self._client: S3Client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            region_name=region,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
        )

    def ensure_bucket(self) -> None:
        """Create the bucket if it doesn't exist (no-op on real S3 where the
        bucket is Terraform-managed; convenient against a fresh MinIO)."""
        from botocore.exceptions import ClientError

        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            log.info("creating bucket", bucket=self._bucket)
            self._client.create_bucket(Bucket=self._bucket)

    def write(self, records: list[dict[str, Any]]) -> str | None:
        """Write a batch as one Parquet object. Returns the object key, or
        None for an empty batch."""
        if not records:
            return None
        body = events_to_parquet(records)
        key = partition_key(self._prefix)
        self._client.put_object(Bucket=self._bucket, Key=key, Body=body)
        log.info("flushed parquet", key=key, events=len(records), bytes=len(body))
        return key
