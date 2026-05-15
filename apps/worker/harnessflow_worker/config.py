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

    @classmethod
    def load(cls) -> WorkerConfig:
        """Build a config from environment variables, applying defaults."""
        return cls(
            temporal_host=os.getenv("TEMPORAL_HOST", "localhost:7233"),
            temporal_namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
            temporal_task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "harnessflow-tasks"),
            environment=os.getenv("ENVIRONMENT", "development"),
        )
