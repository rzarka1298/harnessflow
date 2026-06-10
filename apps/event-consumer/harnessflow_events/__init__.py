"""HarnessFlow event firehose consumer.

Drains the ``harnessflow.workflow.events`` Redpanda topic and writes the
events as date-partitioned Parquet to S3 (MinIO locally). See ADR-0004.
"""

__version__ = "0.1.0"
