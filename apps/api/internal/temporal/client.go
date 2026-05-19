// Package temporal wires the Temporal Go SDK client and worker.
package temporal

import (
	"fmt"

	"go.temporal.io/sdk/client"
)

// Config groups the Temporal connection parameters loaded from the environment.
type Config struct {
	HostPort  string
	Namespace string
	TaskQueue string
}

// NewClient dials the Temporal frontend and returns a configured client.
// Callers are responsible for closing the client.
func NewClient(cfg Config) (client.Client, error) {
	if cfg.HostPort == "" {
		return nil, fmt.Errorf("temporal: HostPort is required")
	}
	if cfg.Namespace == "" {
		cfg.Namespace = "default"
	}
	c, err := client.Dial(client.Options{
		HostPort:  cfg.HostPort,
		Namespace: cfg.Namespace,
	})
	if err != nil {
		return nil, fmt.Errorf("temporal: dial %s: %w", cfg.HostPort, err)
	}
	return c, nil
}
