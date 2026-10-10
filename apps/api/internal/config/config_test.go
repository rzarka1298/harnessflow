package config

import "testing"

func TestOptionalTelemetry(t *testing.T) {
	t.Setenv("OTEL_EXPORTER_OTLP_ENDPOINT_GRPC", "")
	cfg, err := Load()
	if err != nil {
		t.Fatal(err)
	}
	if cfg.OTLPEndpoint != "" {
		t.Fatal("empty endpoint must disable tracing")
	}
	t.Setenv("OTEL_EXPORTER_OTLP_ENDPOINT_GRPC", "localhost:4317")
	cfg, err = Load()
	if err != nil {
		t.Fatal(err)
	}
	if cfg.OTLPEndpoint != "localhost:4317" {
		t.Fatal("configured endpoint was ignored")
	}
}
