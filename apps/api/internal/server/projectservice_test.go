package server

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os/exec"
	"testing"

	"connectrpc.com/connect"
	projectv1 "github.com/rzarka1298/harnessflow/packages/sdk/gen/go/harnessflow/project/v1"
)

func TestProjectLimits(t *testing.T) {
	a, s, err := runLimits(0, 0)
	if err != nil || a != 30 || s != 14400 {
		t.Fatalf("defaults: %d %d %v", a, s, err)
	}
	for _, limits := range [][2]int32{{-1, 60}, {10001, 60}, {1, 59}, {1, 604801}} {
		if _, _, err := runLimits(limits[0], limits[1]); err == nil {
			t.Fatalf("accepted invalid limits %v", limits)
		}
	}
}
func TestCanonicalRepositoryAllowsEmptyGit(t *testing.T) {
	dir := t.TempDir()
	if output, err := exec.Command("git", "init", dir).CombinedOutput(); err != nil {
		t.Fatalf("git init: %s %v", output, err)
	}
	resolved, err := canonicalRepository(context.Background(), dir)
	if err != nil || resolved == "" {
		t.Fatalf("empty repository: %s %v", resolved, err)
	}
	if _, err := canonicalRepository(context.Background(), t.TempDir()); err == nil {
		t.Fatal("accepted non-repository")
	}
	if _, err := canonicalRepository(context.Background(), "relative"); err == nil {
		t.Fatal("accepted relative path")
	}
}
func TestProjectInvalidControlRejectedBeforeStorage(t *testing.T) {
	service := &ProjectService{}
	for _, req := range []*projectv1.ControlRunRequest{
		{RunId: "bad", Action: "cancel"},
		{RunId: "00000000-0000-0000-0000-000000000001", Action: "delete"},
		{RunId: "00000000-0000-0000-0000-000000000001", Action: "resume", AdditionalAttempts: -1},
		{RunId: "00000000-0000-0000-0000-000000000001", Action: "cancel", AdditionalAttempts: 1},
	} {
		if _, err := service.ControlRun(context.Background(), connect.NewRequest(req)); connect.CodeOf(err) != connect.CodeInvalidArgument {
			t.Fatalf("unexpected error %v", err)
		}
	}
}
func TestOriginProtection(t *testing.T) {
	handler := originMiddleware(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusNoContent) }), "http://localhost:3000")
	for _, tt := range []struct {
		origin string
		want   int
	}{{"", 204}, {"http://localhost:3000", 204}, {"https://evil.test", 403}, {"null", 403}, {"http://localhost:3000.evil.test", 403}} {
		req := httptest.NewRequest("POST", "http://localhost:8080/rpc", nil)
		req.Header.Set("Origin", tt.origin)
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		if rec.Code != tt.want {
			t.Fatalf("origin %s: got %d", tt.origin, rec.Code)
		}
	}
	request := httptest.NewRequest("POST", "http://attacker.test:8080/rpc", nil)
	request.Header.Set("Origin", "http://attacker.test:8080")
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	if response.Code != http.StatusForbidden {
		t.Fatal("DNS rebinding Host was accepted")
	}
}
