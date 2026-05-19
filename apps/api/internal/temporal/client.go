// Package temporal wires the Temporal Go SDK client and worker.
package temporal

import (
	"fmt"

	"go.opentelemetry.io/otel"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/contrib/opentelemetry"
	"go.temporal.io/sdk/interceptor"
)

// Config groups the Temporal connection parameters loaded from the environment.
type Config struct {
	HostPort  string
	Namespace string
	TaskQueue string
}

// NewClient dials the Temporal frontend and returns a configured client. The
// client (and any worker created against it) carries an OTel tracing
// interceptor so workflow and activity spans hang off the inbound RPC trace.
//
// Callers are responsible for closing the client.
func NewClient(cfg Config) (client.Client, error) {
	if cfg.HostPort == "" {
		return nil, fmt.Errorf("temporal: HostPort is required")
	}
	if cfg.Namespace == "" {
		cfg.Namespace = "default"
	}
	tracer, err := opentelemetry.NewTracingInterceptor(opentelemetry.TracerOptions{
		Tracer: otel.GetTracerProvider().Tracer("harnessflow-temporal"),
	})
	if err != nil {
		return nil, fmt.Errorf("temporal: tracing interceptor: %w", err)
	}
	c, err := client.Dial(client.Options{
		HostPort:     cfg.HostPort,
		Namespace:    cfg.Namespace,
		Interceptors: []interceptor.ClientInterceptor{tracer},
	})
	if err != nil {
		return nil, fmt.Errorf("temporal: dial %s: %w", cfg.HostPort, err)
	}
	return c, nil
}

// TracingInterceptor returns a fresh Temporal interceptor that integrates with
// the global OTel tracer provider — used to wire workers.
func TracingInterceptor() (interceptor.Interceptor, error) {
	tracer, err := opentelemetry.NewTracingInterceptor(opentelemetry.TracerOptions{
		Tracer: otel.GetTracerProvider().Tracer("harnessflow-temporal"),
	})
	if err != nil {
		return nil, fmt.Errorf("temporal: tracing interceptor: %w", err)
	}
	return tracer, nil
}
