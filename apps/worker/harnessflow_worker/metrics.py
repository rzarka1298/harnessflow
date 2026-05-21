"""OpenTelemetry metrics for the worker.

Instruments are created from the *real* meter inside ``setup_metrics`` rather
than from the global proxy at import time. The proxy path is meant to forward
import-time instruments once a provider is installed, but binding it from a
long-running worker (instruments imported across several activity modules)
proved unreliable — some instruments forwarded, some didn't. Binding to the
provider's own meter after ``set_meter_provider`` is unambiguous.

Metric names omit the ``_total`` suffix and any ``unit=`` — the collector's
Prometheus exporter appends ``_total`` to counters and would otherwise splice
the unit into the name. The exported names are:
    harnessflow_workflow_runs        -> harnessflow_workflow_runs_total
    harnessflow_llm_tokens           -> harnessflow_llm_tokens_total
    harnessflow_llm_cost_usd         -> harnessflow_llm_cost_usd_total
    harnessflow_workflow_duration_seconds (histogram, unchanged)
"""

from __future__ import annotations

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.metrics import Counter, Histogram
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

_runs: Counter | None = None
_duration: Histogram | None = None
_tokens: Counter | None = None
_cost: Counter | None = None


def setup_metrics(
    endpoint: str, service_name: str, environment: str
) -> MeterProvider | None:
    """Install a global MeterProvider exporting OTLP/gRPC to ``endpoint`` and
    bind the module's instruments to it.

    Returns the provider so the caller can force_flush + shut down on exit.
    Empty endpoint disables metrics and returns None.
    """
    global _runs, _duration, _tokens, _cost
    if not endpoint:
        return None

    resource = Resource.create(
        {"service.name": service_name, "deployment.environment.name": environment}
    )
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=True),
        export_interval_millis=5000,
    )
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)

    meter = provider.get_meter("harnessflow.worker")
    _runs = meter.create_counter(
        "harnessflow_workflow_runs",
        description="Workflow runs by terminal status.",
    )
    _duration = meter.create_histogram(
        "harnessflow_workflow_duration_seconds",
        unit="s",
        description="Wall-clock duration of a workflow run.",
    )
    _tokens = meter.create_counter(
        "harnessflow_llm_tokens",
        description="LLM tokens consumed, by model and direction.",
    )
    _cost = meter.create_counter(
        "harnessflow_llm_cost_usd",
        description="LLM spend in USD, by model.",
    )
    return provider


def record_run(workflow: str, status: str, duration_s: float | None) -> None:
    """Emit run-count + (when terminal) duration metrics. No-op if metrics off."""
    if _runs is None:
        return
    _runs.add(1, {"workflow": workflow, "status": status})
    if duration_s is not None and _duration is not None:
        _duration.record(duration_s, {"workflow": workflow})


def record_llm(
    workflow: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd_cents: int,
) -> None:
    """Emit token + cost metrics for one LLM call. No-op if metrics off."""
    if _tokens is None or _cost is None:
        return
    base = {"workflow": workflow, "provider": provider, "model": model}
    _tokens.add(input_tokens, {**base, "type": "input"})
    _tokens.add(output_tokens, {**base, "type": "output"})
    _cost.add(cost_usd_cents / 100.0, base)
