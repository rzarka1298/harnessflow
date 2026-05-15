// Package config loads HarnessFlow API configuration from the environment.
package config

import (
	"fmt"
	"os"
	"strconv"
)

// Config holds all runtime configuration for the API service.
type Config struct {
	APIPort     int
	LogLevel    string
	Environment string
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
