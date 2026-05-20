"""OpenTelemetry SDK init for the Python worker.

Mirrors apps/api/internal/otel: same OTLP/gRPC endpoint (the collector
defined in docker-compose), same W3C propagator, same service-naming
convention. The Temporal Python tracing interceptor reads
``trace.get_tracer_provider()`` so we must install our provider BEFORE
constructing the Temporal worker.
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


def setup_otel(endpoint: str, service_name: str, environment: str) -> TracerProvider | None:
    """Install a global tracer provider that exports OTLP/gRPC to ``endpoint``.

    Returns the provider so callers can shut it down on exit. ``endpoint`` is
    a host:port with no scheme (e.g. ``"localhost:4317"``); empty disables
    tracing and returns None.
    """
    if not endpoint:
        return None
    resource = Resource.create(
        {
            "service.name": service_name,
            "deployment.environment.name": environment,
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    set_global_textmap(TraceContextTextMapPropagator())
    return provider
