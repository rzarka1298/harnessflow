// Package config loads HarnessFlow API configuration from the environment.
package config

import (
	"fmt"
	"os"
	"strconv"
)

// Config holds all runtime configuration for the API service.
type Config struct {
	APIPort           int
	LogLevel          string
	Environment       string
	DatabaseURL       string
	TemporalHost      string
	TemporalNamespace string
	TemporalTaskQueue string
	// OTLPEndpoint is the OTel collector gRPC endpoint (e.g. localhost:4317).
	// Empty disables tracing.
	OTLPEndpoint string
}

// Load reads configuration from environment variables, applying defaults.
func Load() (*Config, error) {
	port, err := envInt("API_PORT", 8080)
	if err != nil {
		return nil, err
	}
	return &Config{
		APIPort:     port,
		LogLevel:    envStr("LOG_LEVEL", "info"),
		Environment: envStr("ENVIRONMENT", "development"),
		DatabaseURL: envStr(
			"DATABASE_URL",
			"postgres://harnessflow:harnessflow@localhost:5432/harnessflow?sslmode=disable",
		),
		TemporalHost:      envStr("TEMPORAL_HOST", "localhost:7233"),
		TemporalNamespace: envStr("TEMPORAL_NAMESPACE", "default"),
		TemporalTaskQueue: envStr("TEMPORAL_TASK_QUEUE", "harnessflow-tasks"),
		OTLPEndpoint:      envStr("OTEL_EXPORTER_OTLP_ENDPOINT_GRPC", "localhost:4317"),
	}, nil
}

func envStr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func envInt(key string, def int) (int, error) {
	v := os.Getenv(key)
	if v == "" {
		return def, nil
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return 0, fmt.Errorf("config: %s must be an integer, got %q", key, v)
	}
	return n, nil
}
