// Command api is the HarnessFlow orchestrator HTTP/RPC entrypoint.
package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"connectrpc.com/otelconnect"
	"go.temporal.io/sdk/interceptor"

	"github.com/rzarka1298/harnessflow/apps/api/internal/config"
	hfotel "github.com/rzarka1298/harnessflow/apps/api/internal/otel"
	"github.com/rzarka1298/harnessflow/apps/api/internal/server"
	"github.com/rzarka1298/harnessflow/apps/api/internal/store"
	hftemporal "github.com/rzarka1298/harnessflow/apps/api/internal/temporal"
	"github.com/rzarka1298/harnessflow/apps/api/internal/workflow"
)

func main() {
	if err := run(); err != nil {
		slog.Error("fatal", slog.String("error", err.Error()))
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load()
	if err != nil {
		return err
	}

	log := newLogger(cfg.LogLevel)
	log.Info("starting harnessflow api",
		slog.Int("port", cfg.APIPort),
		slog.String("environment", cfg.Environment),
	)

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	// --- OpenTelemetry ------------------------------------------------------
	// MUST be initialized BEFORE the Temporal client so the tracing
	// interceptor binds to the right tracer provider.
	otelShutdown, err := hfotel.Setup(ctx, hfotel.Config{
		Endpoint:    cfg.OTLPEndpoint,
		ServiceName: "harnessflow-api",
		Environment: cfg.Environment,
	})
	if err != nil {
		return fmt.Errorf("otel: %w", err)
	}
	defer func() {
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := otelShutdown(shutdownCtx); err != nil {
			log.Error("otel shutdown", slog.String("error", err.Error()))
		}
	}()
	log.Info("otel configured", slog.String("endpoint", cfg.OTLPEndpoint))

	// --- Postgres -----------------------------------------------------------
	pool, err := store.NewPool(ctx, cfg.DatabaseURL)
	if err != nil {
		return fmt.Errorf("postgres: %w", err)
	}
	defer pool.Close()
	queries := store.New(pool)
	log.Info("postgres connected")

	// --- Temporal client + worker ------------------------------------------
	tc, err := hftemporal.NewClient(hftemporal.Config{
		HostPort:  cfg.TemporalHost,
		Namespace: cfg.TemporalNamespace,
		TaskQueue: cfg.TemporalTaskQueue,
	})
	if err != nil {
		return fmt.Errorf("temporal client: %w", err)
	}
	defer tc.Close()
	log.Info("temporal connected", slog.String("host", cfg.TemporalHost))

	tracingInterceptor, err := hftemporal.TracingInterceptor()
	if err != nil {
		return fmt.Errorf("temporal tracing interceptor: %w", err)
	}
	tw := workflow.NewWorker(tc, cfg.TemporalTaskQueue, []interceptor.WorkerInterceptor{tracingInterceptor})
	workerStop := make(chan any)
	workerErrCh := make(chan error, 1)
	go func() { workerErrCh <- tw.Run(workerStop) }()
	defer close(workerStop)
	log.Info("temporal worker started", slog.String("task_queue", cfg.TemporalTaskQueue))

	// --- Connect services + HTTP server -------------------------------------
	connectOTel, err := otelconnect.NewInterceptor(otelconnect.WithTrustRemote())
	if err != nil {
		return fmt.Errorf("otelconnect: %w", err)
	}
	services := server.Services{
		Workflow: &server.WorkflowService{
			Queries:   queries,
			Temporal:  tc,
			TaskQueue: cfg.TemporalTaskQueue,
			Log:       log,
		},
		Run: &server.RunService{Queries: queries},
	}

	srv := &http.Server{
		Addr:              fmt.Sprintf(":%d", cfg.APIPort),
		Handler:           server.New(log, services, connectOTel),
		ReadHeaderTimeout: 10 * time.Second,
	}
	httpErrCh := make(chan error, 1)
	go func() {
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			httpErrCh <- err
		}
	}()
	log.Info("http server listening", slog.Int("port", cfg.APIPort))

	// --- Wait for shutdown or failure --------------------------------------
	select {
	case err := <-httpErrCh:
		return fmt.Errorf("http server: %w", err)
	case err := <-workerErrCh:
		return fmt.Errorf("temporal worker: %w", err)
	case <-ctx.Done():
		log.Info("shutdown signal received")
	}

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		return fmt.Errorf("graceful shutdown failed: %w", err)
	}
	log.Info("shutdown complete")
	return nil
}

func newLogger(level string) *slog.Logger {
	var lvl slog.Level
	if err := lvl.UnmarshalText([]byte(level)); err != nil {
		lvl = slog.LevelInfo
	}
	return slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: lvl}))
}
