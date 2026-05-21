// Package server wires the HarnessFlow API HTTP surface.
//
// As of Week 2 the surface is:
//   - GET  /healthz, /readyz                                (health probes)
//   - Connect: harnessflow.workflow.v1.WorkflowService.*
//   - Connect: harnessflow.run.v1.RunService.*
//
// We use the stdlib http.ServeMux at the routing layer because Connect
// generates handlers that own their own URL prefixes (e.g.
// "/harnessflow.workflow.v1.WorkflowService/") — mounting via Chi would
// rewrite the path. A small slog logging middleware wraps everything.
package server

import (
	"connectrpc.com/connect"
	"encoding/json"
	"log/slog"
	"net/http"
	"time"

	"github.com/rzarka1298/harnessflow/packages/sdk/gen/go/harnessflow/run/v1/runv1connect"
	"github.com/rzarka1298/harnessflow/packages/sdk/gen/go/harnessflow/workflow/v1/workflowv1connect"
)

// Services groups the implementations the router exposes.
type Services struct {
	Workflow workflowv1connect.WorkflowServiceHandler
	Run      runv1connect.RunServiceHandler
}

// New builds the API HTTP handler.
//
// interceptor is applied to every Connect handler; pass nil to skip.
func New(log *slog.Logger, svc Services, interceptor connect.Interceptor) http.Handler {
	mux := http.NewServeMux()

	mux.HandleFunc("/healthz", healthz)
	mux.HandleFunc("/readyz", readyz)

	var opts []connect.HandlerOption
	if interceptor != nil {
		opts = append(opts, connect.WithInterceptors(interceptor))
	}

	wfPath, wfHandler := workflowv1connect.NewWorkflowServiceHandler(svc.Workflow, opts...)
	mux.Handle(wfPath, wfHandler)
	runPath, runHandler := runv1connect.NewRunServiceHandler(svc.Run, opts...)
	mux.Handle(runPath, runHandler)

	return logMiddleware(log, corsMiddleware(mux))
}

// corsMiddleware lets the browser dashboard (typically http://localhost:3000)
// call the API at http://localhost:8080 in dev. Connect uses a small set of
// custom headers (Connect-Protocol-Version, Connect-Timeout-Ms,
// Content-Encoding) plus the standard Content-Type. Production deployments
// should override this with a stricter allowlist via an env-driven config.
func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set(
			"Access-Control-Allow-Headers",
			"Content-Type, Connect-Protocol-Version, Connect-Timeout-Ms, X-User-Agent",
		)
		w.Header().Set("Access-Control-Expose-Headers", "Content-Encoding, Vary")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func healthz(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func readyz(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ready"})
}

func writeJSON(w http.ResponseWriter, code int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(body)
}

// logMiddleware emits one slog line per request. Lightweight; per-RPC tracing
// comes from the Connect OTel interceptor.
func logMiddleware(log *slog.Logger, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		sw := &statusWriter{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(sw, r)
		log.Info("request",
			slog.String("method", r.Method),
			slog.String("path", r.URL.Path),
			slog.Int("status", sw.status),
			slog.Duration("duration", time.Since(start)),
		)
	})
}

type statusWriter struct {
	http.ResponseWriter
	status int
}

func (s *statusWriter) WriteHeader(code int) {
	s.status = code
	s.ResponseWriter.WriteHeader(code)
}
