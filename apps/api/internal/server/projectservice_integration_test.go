package server

import (
	"context"
	"log/slog"
	"os"
	"path/filepath"
	"testing"

	"connectrpc.com/connect"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	projectv1 "github.com/rzarka1298/harnessflow/packages/sdk/gen/go/harnessflow/project/v1"
	"github.com/stretchr/testify/mock"
	"go.temporal.io/sdk/mocks"
)

// Opt-in integration tests use an isolated schema and leave existing data alone.
func TestProjectLifecyclePersistence(t *testing.T) {
	dsn := os.Getenv("HARNESSFLOW_TEST_DATABASE_URL")
	if dsn == "" {
		t.Skip("set HARNESSFLOW_TEST_DATABASE_URL to run Postgres integration tests")
	}
	ctx := context.Background()
	admin, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer admin.Close()
	schema := "project_test_" + uuid.NewString()
	quoted := "\"" + schema + "\""
	if _, err := admin.Exec(ctx, "CREATE SCHEMA "+quoted); err != nil {
		t.Fatal(err)
	}
	defer func() {
		if _, err := admin.Exec(ctx, "DROP SCHEMA "+quoted+" CASCADE"); err != nil {
			t.Error(err)
		}
	}()
	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		t.Fatal(err)
	}
	cfg.ConnConfig.RuntimeParams["search_path"] = quoted
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	defer pool.Close()
	migration, err := os.ReadFile(filepath.Join("..", "..", "migrations", "0004_projects.up.sql"))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, string(migration)); err != nil {
		t.Fatal(err)
	}
	controlMigration, err := os.ReadFile(filepath.Join("..", "..", "migrations", "0005_project_control_version.up.sql"))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, string(controlMigration)); err != nil {
		t.Fatal(err)
	}
	projectID := uuid.NewString()
	if _, err := pool.Exec(ctx, "INSERT INTO projects(id,name,repository_path,prd) VALUES($1,'test','/fixture/repo','build it')", projectID); err != nil {
		t.Fatal(err)
	}
	temporal := &mocks.Client{}
	temporal.On("ExecuteWorkflow", mock.Anything, mock.Anything, mock.Anything, mock.Anything).Return(nil, nil)
	temporal.On("SignalWorkflow", mock.Anything, mock.Anything, "", mock.Anything, mock.Anything).Return(nil)
	service := &ProjectService{Pool: pool, Temporal: temporal, TaskQueue: "test", Log: slog.Default()}
	started, err := service.StartRun(ctx, connect.NewRequest(&projectv1.StartRunRequest{ProjectId: projectID}))
	if err != nil {
		t.Fatal(err)
	}
	id := started.Msg.Run.Id
	if _, err := service.StartRun(ctx, connect.NewRequest(&projectv1.StartRunRequest{ProjectId: projectID})); connect.CodeOf(err) != connect.CodeAlreadyExists {
		t.Fatalf("duplicate run: %v", err)
	}
	otherProject := uuid.NewString()
	if _, err := pool.Exec(ctx, "INSERT INTO projects(id,name,repository_path,prd) VALUES($1,'other','/fixture/repo','another task')", otherProject); err != nil {
		t.Fatal(err)
	}
	if _, err := service.StartRun(ctx, connect.NewRequest(&projectv1.StartRunRequest{ProjectId: otherProject})); connect.CodeOf(err) != connect.CodeAlreadyExists {
		t.Fatalf("same repository across projects: %v", err)
	}
	if _, err := pool.Exec(ctx, "UPDATE project_runs SET status='exhausted',state='{\"checkpoint\":1}' WHERE id=$1", id); err != nil {
		t.Fatal(err)
	}
	if _, err := service.ControlRun(ctx, connect.NewRequest(&projectv1.ControlRunRequest{RunId: id, Action: "resume", AdditionalAttempts: 5, Clarification: "keep API compatible"})); err != nil {
		t.Fatal(err)
	}
	var attempts, revision int
	var control, state string
	if err := pool.QueryRow(ctx, "SELECT max_attempts,control,state::text,control_version FROM project_runs WHERE id=$1", id).Scan(&attempts, &control, &state, &revision); err != nil {
		t.Fatal(err)
	}
	if attempts != 35 || control != "resume" || state != "{\"checkpoint\": 1}" || revision != 1 {
		t.Fatalf("resume changed wrong state: %d %s %s", attempts, control, state)
	}
	// Retrying a saved resume must not grant the same extension twice.
	if _, err := service.ControlRun(ctx, connect.NewRequest(&projectv1.ControlRunRequest{RunId: id, Action: "resume", AdditionalAttempts: 5})); connect.CodeOf(err) != connect.CodeFailedPrecondition {
		t.Fatalf("duplicate resume: %v", err)
	}
	if err := pool.QueryRow(ctx, "SELECT max_attempts,control,control_version FROM project_runs WHERE id=$1", id).Scan(&attempts, &control, &revision); err != nil {
		t.Fatal(err)
	}
	if attempts != 35 || control != "resume" || revision != 1 {
		t.Fatalf("duplicate resume changed saved control: %d %s %d", attempts, control, revision)
	}
	if _, err := pool.Exec(ctx, "UPDATE project_runs SET status='running',control='' WHERE id=$1", id); err != nil {
		t.Fatal(err)
	}
	if _, err := service.ControlRun(ctx, connect.NewRequest(&projectv1.ControlRunRequest{RunId: id, Action: "resume", AdditionalAttempts: 5})); connect.CodeOf(err) != connect.CodeFailedPrecondition {
		t.Fatalf("resume while running: %v", err)
	}
	if _, err := pool.Exec(ctx, "UPDATE project_runs SET status='blocked',control='cancel' WHERE id=$1", id); err != nil {
		t.Fatal(err)
	}
	if _, err := service.ControlRun(ctx, connect.NewRequest(&projectv1.ControlRunRequest{RunId: id, Action: "resume", AdditionalAttempts: 5})); connect.CodeOf(err) != connect.CodeFailedPrecondition {
		t.Fatalf("resume over pending cancel: %v", err)
	}
	if err := pool.QueryRow(ctx, "SELECT max_attempts,control,control_version FROM project_runs WHERE id=$1", id).Scan(&attempts, &control, &revision); err != nil {
		t.Fatal(err)
	}
	if attempts != 35 || control != "cancel" || revision != 1 {
		t.Fatalf("rejected resume changed pending cancel: %d %s %d", attempts, control, revision)
	}
	if _, err := pool.Exec(ctx, "UPDATE project_runs SET status='completed' WHERE id=$1", id); err != nil {
		t.Fatal(err)
	}
	if _, err := service.ControlRun(ctx, connect.NewRequest(&projectv1.ControlRunRequest{RunId: id, Action: "resume"})); connect.CodeOf(err) != connect.CodeFailedPrecondition {
		t.Fatalf("terminal resume: %v", err)
	}
	if _, err := service.StartRun(ctx, connect.NewRequest(&projectv1.StartRunRequest{ProjectId: projectID})); err != nil {
		t.Fatalf("new run after completion: %v", err)
	}
}
