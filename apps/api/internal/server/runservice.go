package server

import (
	"context"
	"errors"
	"fmt"
	"strconv"

	"connectrpc.com/connect"
	"github.com/jackc/pgx/v5"
	"go.temporal.io/sdk/client"

	runv1 "github.com/rzarka1298/harnessflow/packages/sdk/gen/go/harnessflow/run/v1"
	"github.com/rzarka1298/harnessflow/packages/sdk/gen/go/harnessflow/run/v1/runv1connect"

	"github.com/rzarka1298/harnessflow/apps/api/internal/store"
	"github.com/rzarka1298/harnessflow/apps/api/internal/workflow"
)

// RunService implements runv1connect.RunServiceHandler.
type RunService struct {
	Queries  *store.Queries
	Temporal client.Client
}

var _ runv1connect.RunServiceHandler = (*RunService)(nil)

// GetRun returns a single run plus its steps.
func (s *RunService) GetRun(
	ctx context.Context,
	req *connect.Request[runv1.GetRunRequest],
) (*connect.Response[runv1.GetRunResponse], error) {
	pgID, err := uuidFromString(req.Msg.GetId())
	if err != nil {
		return nil, connect.NewError(connect.CodeInvalidArgument, fmt.Errorf("invalid id: %w", err))
	}
	run, err := s.Queries.GetRun(ctx, pgID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, connect.NewError(connect.CodeNotFound, fmt.Errorf("run not found"))
		}
		return nil, connect.NewError(connect.CodeInternal, err)
	}
	stepsRows, err := s.Queries.ListStepsByRun(ctx, pgID)
	if err != nil {
		return nil, connect.NewError(connect.CodeInternal, err)
	}
	steps := make([]*runv1.Step, len(stepsRows))
	for i, r := range stepsRows {
		steps[i] = toProtoStep(r)
	}
	return connect.NewResponse(&runv1.GetRunResponse{
		Run:   toProtoRun(run),
		Steps: steps,
	}), nil
}

// ListRuns returns runs newest-first; if workflow_id is set, restricted to
// that workflow.
func (s *RunService) ListRuns(
	ctx context.Context,
	req *connect.Request[runv1.ListRunsRequest],
) (*connect.Response[runv1.ListRunsResponse], error) {
	size := pageSize(req.Msg.GetPageSize())
	offset := offsetFromToken(req.Msg.GetPageToken())

	var rows []store.WorkflowRun
	var err error
	if req.Msg.GetWorkflowId() != "" {
		pgID, e := uuidFromString(req.Msg.GetWorkflowId())
		if e != nil {
			return nil, connect.NewError(connect.CodeInvalidArgument, fmt.Errorf("invalid workflow_id: %w", e))
		}
		rows, err = s.Queries.ListRunsByWorkflow(ctx, store.ListRunsByWorkflowParams{
			WorkflowID: pgID,
			Limit:      size,
			Offset:     offset,
		})
	} else {
		rows, err = s.Queries.ListRuns(ctx, store.ListRunsParams{
			Limit:  size,
			Offset: offset,
		})
	}
	if err != nil {
		return nil, connect.NewError(connect.CodeInternal, err)
	}
	out := make([]*runv1.Run, len(rows))
	for i, r := range rows {
		out[i] = toProtoRun(r)
	}
	resp := &runv1.ListRunsResponse{Runs: out}
	if int32(len(rows)) == size {
		resp.NextPageToken = tokenFromOffset(offset + int32(len(rows)))
	}
	return connect.NewResponse(resp), nil
}

// ApproveRun releases a run paused on an approval gate by sending the approve
// signal to its Temporal workflow.
func (s *RunService) ApproveRun(
	ctx context.Context,
	req *connect.Request[runv1.ApproveRunRequest],
) (*connect.Response[runv1.ApproveRunResponse], error) {
	pgID, err := uuidFromString(req.Msg.GetRunId())
	if err != nil {
		return nil, connect.NewError(connect.CodeInvalidArgument, fmt.Errorf("invalid run_id: %w", err))
	}
	run, err := s.Queries.GetRun(ctx, pgID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, connect.NewError(connect.CodeNotFound, fmt.Errorf("run not found"))
		}
		return nil, connect.NewError(connect.CodeInternal, err)
	}
	// SignalWorkflow with an empty run id targets the latest run of the
	// workflow id — correct here since each HarnessFlow run is its own
	// Temporal workflow id.
	if err := s.Temporal.SignalWorkflow(
		ctx, run.TemporalWorkflowID, "", workflow.SignalApprove,
		workflow.ApprovalSignal{ApprovedBy: "dashboard"},
	); err != nil {
		return nil, connect.NewError(connect.CodeInternal, fmt.Errorf("signal: %w", err))
	}
	return connect.NewResponse(&runv1.ApproveRunResponse{}), nil
}

// --- pagination helpers (shared with WorkflowService) ----------------------

func pageSize(req int32) int32 {
	const def, max = int32(50), int32(200)
	switch {
	case req <= 0:
		return def
	case req > max:
		return max
	default:
		return req
	}
}

func offsetFromToken(t string) int32 {
	if t == "" {
		return 0
	}
	n, err := strconv.Atoi(t)
	if err != nil || n < 0 {
		return 0
	}
	return int32(n)
}

func tokenFromOffset(off int32) string {
	return strconv.Itoa(int(off))
}
