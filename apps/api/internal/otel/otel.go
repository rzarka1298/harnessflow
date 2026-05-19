// Package otel wires the OpenTelemetry SDK for the API process — a tracer
// provider that exports via OTLP/gRPC to the collector defined in
// docker-compose.yml. Returned shutdown func must be called before exit so
// in-flight spans flush.
package otel

import (
	"context"
	"fmt"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.27.0"
	"go.opentelemetry.io/otel/trace"
)

// Config describes the OTel runtime parameters.
type Config struct {
	// Endpoint is an OTLP gRPC target, e.g. "localhost:4317". Empty disables
	// tracing entirely (Setup returns a no-op shutdown).
	Endpoint    string
	ServiceName string
	Environment string
}

// Setup installs the global tracer provider + W3C propagator and returns a
// shutdown func.
func Setup(ctx context.Context, cfg Config) (func(context.Context) error, error) {
	noop := func(context.Context) error { return nil }
	if cfg.Endpoint == "" {
		return noop, nil
	}
	res, err := resource.New(ctx, resource.WithAttributes(
		semconv.ServiceName(cfg.ServiceName),
		// The semconv package renames this attribute between versions; setting
		// the key explicitly keeps us decoupled from churn.
		attribute.String("deployment.environment.name", cfg.Environment),
	))
	if err != nil {
		return nil, fmt.Errorf("otel: resource: %w", err)
	}
	exp, err := otlptrace.New(ctx, otlptracegrpc.NewClient(
		otlptracegrpc.WithEndpoint(cfg.Endpoint),
		otlptracegrpc.WithInsecure(),
	))
	if err != nil {
		return nil, fmt.Errorf("otel: otlp exporter: %w", err)
	}
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exp),
		sdktrace.WithResource(res),
	)
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))
	return tp.Shutdown, nil
}

// Tracer returns the API's named tracer, used for explicit spans.
func Tracer() trace.Tracer {
	return otel.Tracer("harnessflow-api")
}
