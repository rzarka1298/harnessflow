package server

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"connectrpc.com/connect"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/rzarka1298/harnessflow/apps/api/internal/workflow"
	projectv1 "github.com/rzarka1298/harnessflow/packages/sdk/gen/go/harnessflow/project/v1"
	enumspb "go.temporal.io/api/enums/v1"
	"go.temporal.io/api/serviceerror"
	"go.temporal.io/sdk/client"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// ProjectService manages durable local coding projects and run controls.
type ProjectService struct {
	Pool      *pgxpool.Pool
	Temporal  client.Client
	TaskQueue string
	Log       *slog.Logger
}

const projectColumns = "id::text, name, repository_path, prd, created_at"
const projectRunColumns = "id::text, project_id::text, status, reason, state::text, created_at, updated_at"

func scanProject(row pgx.Row) (*projectv1.Project, error) {
	p := &projectv1.Project{}
	var created time.Time
	err := row.Scan(&p.Id, &p.Name, &p.RepositoryPath, &p.Prd, &created)
	p.CreatedAt = timestamppb.New(created)
	return p, err
}
func scanProjectRun(row pgx.Row) (*projectv1.ProjectRun, error) {
	r := &projectv1.ProjectRun{}
	var created, updated time.Time
	err := row.Scan(&r.Id, &r.ProjectId, &r.Status, &r.Reason, &r.SnapshotJson, &created, &updated)
	r.CreatedAt = timestamppb.New(created)
	r.UpdatedAt = timestamppb.New(updated)
	return r, err
}
func projectError(err error) error {
	if errors.Is(err, pgx.ErrNoRows) {
		return connect.NewError(connect.CodeNotFound, errors.New("project or run not found"))
	}
	var pgerr *pgconn.PgError
	if errors.As(err, &pgerr) && pgerr.Code == "23505" {
		return connect.NewError(connect.CodeAlreadyExists, errors.New("this repository already has an unfinished run; resume or cancel it first"))
	}
	return connect.NewError(connect.CodeInternal, err)
}
func validID(id string) error {
	if _, err := uuid.Parse(id); err != nil {
		return connect.NewError(connect.CodeInvalidArgument, errors.New("invalid UUID"))
	}
	return nil
}
func canonicalRepository(ctx context.Context, path string) (string, error) {
	if !filepath.IsAbs(path) {
		return "", errors.New("repository_path must be absolute")
	}
	resolved, err := filepath.EvalSymlinks(path)
	if err != nil {
		return "", err
	}
	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	out, err := exec.CommandContext(ctx, "git", "-C", resolved, "rev-parse", "--show-toplevel").Output()
	if err != nil {
		return "", errors.New("repository_path must identify a local non-bare Git repository")
	}
	return filepath.EvalSymlinks(strings.TrimSpace(string(out)))
}

// CreateProject registers a PRD and canonical local Git repository.
func (s *ProjectService) CreateProject(ctx context.Context, req *connect.Request[projectv1.CreateProjectRequest]) (*connect.Response[projectv1.CreateProjectResponse], error) {
	name, prd := strings.TrimSpace(req.Msg.Name), strings.TrimSpace(req.Msg.Prd)
	if name == "" || len(name) > 200 || prd == "" || len(prd) > 1_000_000 {
		return nil, connect.NewError(connect.CodeInvalidArgument, errors.New("name (1–200 bytes) and PRD (1–1000000 bytes) are required"))
	}
	path, err := canonicalRepository(ctx, req.Msg.RepositoryPath)
	if err != nil {
		return nil, connect.NewError(connect.CodeInvalidArgument, err)
	}
	p, err := scanProject(s.Pool.QueryRow(ctx, "INSERT INTO projects(id,name,repository_path,prd) VALUES($1,$2,$3,$4) RETURNING "+projectColumns, uuid.NewString(), name, path, prd))
	if err != nil {
		return nil, projectError(err)
	}
	return connect.NewResponse(&projectv1.CreateProjectResponse{Project: p}), nil
}

// GetProject returns a project definition.
func (s *ProjectService) GetProject(ctx context.Context, req *connect.Request[projectv1.GetProjectRequest]) (*connect.Response[projectv1.GetProjectResponse], error) {
	if err := validID(req.Msg.Id); err != nil {
		return nil, err
	}
	p, err := scanProject(s.Pool.QueryRow(ctx, "SELECT "+projectColumns+" FROM projects WHERE id=$1", req.Msg.Id))
	if err != nil {
		return nil, projectError(err)
	}
	return connect.NewResponse(&projectv1.GetProjectResponse{Project: p}), nil
}

// ListProjects returns projects newest first.
func (s *ProjectService) ListProjects(ctx context.Context, req *connect.Request[projectv1.ListProjectsRequest]) (*connect.Response[projectv1.ListProjectsResponse], error) {
	size, offset := pageSize(req.Msg.PageSize), offsetFromToken(req.Msg.PageToken)
	rows, err := s.Pool.Query(ctx, "SELECT "+projectColumns+" FROM projects ORDER BY created_at DESC,id DESC LIMIT $1 OFFSET $2", size, offset)
	if err != nil {
		return nil, projectError(err)
	}
	defer rows.Close()
	resp := &projectv1.ListProjectsResponse{}
	for rows.Next() {
		p, err := scanProject(rows)
		if err != nil {
			return nil, projectError(err)
		}
		resp.Projects = append(resp.Projects, p)
	}
	if err := rows.Err(); err != nil {
		return nil, projectError(err)
	}
	if len(resp.Projects) == int(size) {
		resp.NextPageToken = tokenFromOffset(offset + size)
	}
	return connect.NewResponse(resp), nil
}
func runLimits(attempts, seconds int32) (int32, int32, error) {
	if attempts == 0 {
		attempts = 30
	}
	if seconds == 0 {
		seconds = 14400
	}
	if attempts < 1 || attempts > 10000 || seconds < 60 || seconds > 604800 {
		return 0, 0, connect.NewError(connect.CodeInvalidArgument, errors.New("attempts must be 1–10000 and duration 60–604800 seconds"))
	}
	return attempts, seconds, nil
}

// StartRun durably queues one run, excluding concurrent work on the repository.
func (s *ProjectService) StartRun(ctx context.Context, req *connect.Request[projectv1.StartRunRequest]) (*connect.Response[projectv1.StartRunResponse], error) {
	if err := validID(req.Msg.ProjectId); err != nil {
		return nil, err
	}
	attempts, seconds, err := runLimits(req.Msg.MaxAttempts, req.Msg.MaxDurationSeconds)
	if err != nil {
		return nil, err
	}
	if len(req.Msg.Model) > 200 {
		return nil, connect.NewError(connect.CodeInvalidArgument, errors.New("model too long"))
	}
	r, err := scanProjectRun(s.Pool.QueryRow(ctx, "INSERT INTO project_runs(id,project_id,repository_path,max_attempts,max_duration_seconds,model,request_pr) SELECT $1,id,repository_path,$3,$4,$5,$6 FROM projects WHERE id=$2 RETURNING "+projectRunColumns, uuid.NewString(), req.Msg.ProjectId, attempts, seconds, req.Msg.Model, req.Msg.RequestPr))
	if err != nil {
		return nil, projectError(err)
	}
	// The durable queued row is the outbox: a transient Temporal outage never
	// loses the request, and the reconciler retries its stable workflow ID.
	if err := s.start(ctx, r.Id); err != nil {
		s.Log.Warn("project queued awaiting Temporal", "run_id", r.Id, "error", err)
	}
	return connect.NewResponse(&projectv1.StartRunResponse{Run: r}), nil
}

// GetRun returns the worker's latest durable snapshot.
func (s *ProjectService) GetRun(ctx context.Context, req *connect.Request[projectv1.GetRunRequest]) (*connect.Response[projectv1.GetRunResponse], error) {
	if err := validID(req.Msg.Id); err != nil {
		return nil, err
	}
	r, err := scanProjectRun(s.Pool.QueryRow(ctx, "SELECT "+projectRunColumns+" FROM project_runs WHERE id=$1", req.Msg.Id))
	if err != nil {
		return nil, projectError(err)
	}
	return connect.NewResponse(&projectv1.GetRunResponse{Run: r}), nil
}

// ListRuns returns project runs newest first.
func (s *ProjectService) ListRuns(ctx context.Context, req *connect.Request[projectv1.ListRunsRequest]) (*connect.Response[projectv1.ListRunsResponse], error) {
	if req.Msg.ProjectId != "" {
		if err := validID(req.Msg.ProjectId); err != nil {
			return nil, err
		}
	}
	size, offset := pageSize(req.Msg.PageSize), offsetFromToken(req.Msg.PageToken)
	rows, err := s.Pool.Query(ctx, "SELECT "+projectRunColumns+" FROM project_runs WHERE ($1='' OR project_id::text=$1) ORDER BY created_at DESC,id DESC LIMIT $2 OFFSET $3", req.Msg.ProjectId, size, offset)
	if err != nil {
		return nil, projectError(err)
	}
	defer rows.Close()
	resp := &projectv1.ListRunsResponse{}
	for rows.Next() {
		r, err := scanProjectRun(rows)
		if err != nil {
			return nil, projectError(err)
		}
		resp.Runs = append(resp.Runs, r)
	}
	if err := rows.Err(); err != nil {
		return nil, projectError(err)
	}
	if len(resp.Runs) == int(size) {
		resp.NextPageToken = tokenFromOffset(offset + size)
	}
	return connect.NewResponse(resp), nil
}

// ControlRun saves a control command before sending a best-effort wake signal.
func (s *ProjectService) ControlRun(ctx context.Context, req *connect.Request[projectv1.ControlRunRequest]) (*connect.Response[projectv1.ControlRunResponse], error) {
	q := req.Msg
	if err := validID(q.RunId); err != nil {
		return nil, err
	}
	if q.Action != "pause" && q.Action != "resume" && q.Action != "cancel" {
		return nil, connect.NewError(connect.CodeInvalidArgument, errors.New("action must be pause, resume, or cancel"))
	}
	if q.AdditionalAttempts < 0 || q.AdditionalAttempts > 10000 || q.AdditionalSeconds < 0 || q.AdditionalSeconds > 604800 || len(q.Clarification) > 100000 {
		return nil, connect.NewError(connect.CodeInvalidArgument, errors.New("invalid limit extension or clarification"))
	}
	if q.Action != "resume" && (q.AdditionalAttempts != 0 || q.AdditionalSeconds != 0 || q.Clarification != "") {
		return nil, connect.NewError(connect.CodeInvalidArgument, errors.New("extensions and clarification require resume"))
	}
	r, err := scanProjectRun(s.Pool.QueryRow(ctx, `UPDATE project_runs SET control=$2, control_version=control_version+1, clarification=CASE WHEN $3='' THEN clarification ELSE $3 END,max_attempts=max_attempts+$4,max_duration_seconds=max_duration_seconds+$5,updated_at=NOW() WHERE id=$1 AND status NOT IN ('completed','failed','canceled') AND ($2 <> 'resume' OR (status IN ('paused','blocked','exhausted') AND control='')) RETURNING `+projectRunColumns, q.RunId, q.Action, q.Clarification, q.AdditionalAttempts, q.AdditionalSeconds))
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, connect.NewError(connect.CodeFailedPrecondition, errors.New("run is terminal, not paused, or already has a pending control"))
	}
	if err != nil {
		return nil, projectError(err)
	}
	if err := s.Temporal.SignalWorkflow(ctx, "hf-project-"+q.RunId, "", workflow.ProjectControlSignal, q.Action); err != nil {
		s.Log.Warn("project control saved awaiting delivery", "run_id", q.RunId, "error", err)
	}
	return connect.NewResponse(&projectv1.ControlRunResponse{Run: r}), nil
}

// GetArtifacts returns the snapshot containing branch, diff, and evidence references.
func (s *ProjectService) GetArtifacts(ctx context.Context, req *connect.Request[projectv1.GetArtifactsRequest]) (*connect.Response[projectv1.GetArtifactsResponse], error) {
	r, err := s.GetRun(ctx, connect.NewRequest(&projectv1.GetRunRequest{Id: req.Msg.RunId}))
	if err != nil {
		return nil, err
	}
	return connect.NewResponse(&projectv1.GetArtifactsResponse{SnapshotJson: r.Msg.Run.SnapshotJson}), nil
}
func (s *ProjectService) start(ctx context.Context, id string) error {
	_, err := s.Temporal.ExecuteWorkflow(ctx, client.StartWorkflowOptions{ID: "hf-project-" + id, TaskQueue: s.TaskQueue, WorkflowIDReusePolicy: enumspb.WORKFLOW_ID_REUSE_POLICY_REJECT_DUPLICATE}, workflow.ProjectWorkflowName, workflow.ProjectInput{RunID: id})
	var exists *serviceerror.WorkflowExecutionAlreadyStarted
	if errors.As(err, &exists) {
		return nil
	}
	return err
}

// ReconcileProjects repairs the database/Temporal start and signal crash windows.
func (s *ProjectService) ReconcileProjects(ctx context.Context) {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()
	for {
		if err := s.reconcile(ctx); err != nil && ctx.Err() == nil {
			s.Log.Warn("project reconciliation failed", "error", err)
		}
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}
func (s *ProjectService) reconcile(ctx context.Context) error {
	rows, err := s.Pool.Query(ctx, "SELECT id::text,control FROM project_runs WHERE status NOT IN ('completed','failed','canceled')")
	if err != nil {
		return err
	}
	type pending struct{ id, control string }
	var runs []pending
	for rows.Next() {
		var r pending
		if err := rows.Scan(&r.id, &r.control); err != nil {
			rows.Close()
			return err
		}
		runs = append(runs, r)
	}
	err = rows.Err()
	rows.Close()
	if err != nil {
		return err
	}
	for _, r := range runs {
		if err := s.start(ctx, r.id); err != nil {
			return fmt.Errorf("start %s: %w", r.id, err)
		}
		description, err := s.Temporal.DescribeWorkflowExecution(ctx, "hf-project-"+r.id, "")
		if err != nil {
			return err
		}
		if info := description.GetWorkflowExecutionInfo(); info != nil {
			status := info.GetStatus()
			if status != enumspb.WORKFLOW_EXECUTION_STATUS_RUNNING && status != enumspb.WORKFLOW_EXECUTION_STATUS_CONTINUED_AS_NEW && status != enumspb.WORKFLOW_EXECUTION_STATUS_UNSPECIFIED {
				terminal := "failed"
				if status == enumspb.WORKFLOW_EXECUTION_STATUS_CANCELED {
					terminal = "canceled"
				}
				_, err := s.Pool.Exec(ctx, "UPDATE project_runs SET status=$2,reason=$3,updated_at=NOW() WHERE id=$1 AND status NOT IN ('completed','failed','canceled')", r.id, terminal, "Temporal execution ended without a terminal checkpoint: "+status.String())
				if err != nil {
					return err
				}
				continue
			}
		}
		if r.control != "" {
			if err := s.Temporal.SignalWorkflow(ctx, "hf-project-"+r.id, "", workflow.ProjectControlSignal, r.control); err != nil {
				return err
			}
		}
	}
	return nil
}
