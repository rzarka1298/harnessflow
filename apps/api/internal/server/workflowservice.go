package server

import (
	"context"
	"errors"
	"fmt"
	"log/slog"

	"connectrpc.com/connect"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
	"go.opentelemetry.io/otel/trace"
	"go.temporal.io/sdk/client"

	workflowv1 "github.com/rzarka1298/harnessflow/packages/sdk/gen/go/harnessflow/workflow/v1"
	"github.com/rzarka1298/harnessflow/packages/sdk/gen/go/harnessflow/workflow/v1/workflowv1connect"

	"github.com/rzarka1298/harnessflow/apps/api/internal/store"
	"github.com/rzarka1298/harnessflow/apps/api/internal/workflow"
)

// WorkflowService implements workflowv1connect.WorkflowServiceHandler.
type WorkflowService struct {
	Queries   *store.Queries
	Temporal  client.Client
	TaskQueue string
	Log       *slog.Logger
}

// Compile-time assertion: WorkflowService satisfies the generated handler.
var _ workflowv1connect.WorkflowServiceHandler = (*WorkflowService)(nil)

// CreateWorkflow validates the submitted YAML, persists it as version=1, and
// activates it. Versioning by name lands when we add upsert semantics; for
// Week 2 every create is a new id at version=1.
func (s *WorkflowService) CreateWorkflow(
	ctx context.Context,
	req *connect.Request[workflowv1.CreateWorkflowRequest],
) (*connect.Response[workflowv1.CreateWorkflowResponse], error) {
	yamlSrc := req.Msg.GetYamlSource()
	parsed, _, err := workflow.Parse(yamlSrc)
	if err != nil {
		return nil, connect.NewError(connect.CodeInvalidArgument, err)
	}

	id, err := uuid.NewV7()
	if err != nil {
		return nil, connect.NewError(connect.CodeInternal, fmt.Errorf("uuid: %w", err))
	}
	description := ""
	if parsed.Description != nil {
		description = *parsed.Description
	}

	created, err := s.Queries.CreateWorkflow(ctx, store.CreateWorkflowParams{
		ID:          pgtype.UUID{Bytes: id, Valid: true},
		Name:        parsed.Name,
		Version:     int32(parsed.Version),
		Description: description,
		YamlSource:  yamlSrc,
		Status:      "active",
	})
	if err != nil {
		return nil, connect.NewError(connect.CodeInternal, fmt.Errorf("store: create: %w", err))
	}
	s.Log.Info("workflow created", "id", uuidToString(created.ID), "name", created.Name, "version", created.Version)
	return connect.NewResponse(&workflowv1.CreateWorkflowResponse{Workflow: toProtoWorkflow(created)}), nil
}

// GetWorkflow returns a single workflow by id.
func (s *WorkflowService) GetWorkflow(
	ctx context.Context,
	req *connect.Request[workflowv1.GetWorkflowRequest],
) (*connect.Response[workflowv1.GetWorkflowResponse], error) {
	pgID, err := uuidFromString(req.Msg.GetId())
	if err != nil {
		return nil, connect.NewError(connect.CodeInvalidArgument, fmt.Errorf("invalid id: %w", err))
	}
	w, err := s.Queries.GetWorkflow(ctx, pgID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, connect.NewError(connect.CodeNotFound, fmt.Errorf("workflow not found"))
		}
		return nil, connect.NewError(connect.CodeInternal, err)
	}
	return connect.NewResponse(&workflowv1.GetWorkflowResponse{Workflow: toProtoWorkflow(w)}), nil
}

// ListWorkflows returns workflows newest-first, paginated by simple offset.
// page_token is the integer offset as a string; empty means start. This is
// good enough for Week 2; cursor pagination lands when it matters.
func (s *WorkflowService) ListWorkflows(
	ctx context.Context,
	req *connect.Request[workflowv1.ListWorkflowsRequest],
) (*connect.Response[workflowv1.ListWorkflowsResponse], error) {
	size := pageSize(req.Msg.GetPageSize())
	offset := offsetFromToken(req.Msg.GetPageToken())

	rows, err := s.Queries.ListWorkflows(ctx, store.ListWorkflowsParams{
		Limit:  size,
		Offset: offset,
	})
	if err != nil {
		return nil, connect.NewError(connect.CodeInternal, err)
	}
	out := make([]*workflowv1.Workflow, len(rows))
	for i, r := range rows {
		out[i] = toProtoWorkflow(r)
	}
	resp := &workflowv1.ListWorkflowsResponse{Workflows: out}
	if int32(len(rows)) == size {
		resp.NextPageToken = tokenFromOffset(offset + int32(len(rows)))
	}
	return connect.NewResponse(resp), nil
}

// RunWorkflow compiles the stored workflow YAML and starts a Temporal workflow.
// The workflow_runs row is created BEFORE the Temporal start so the API can
// return run_id atomically; on Temporal failure the row is marked failed.
func (s *WorkflowService) RunWorkflow(
	ctx context.Context,
	req *connect.Request[workflowv1.RunWorkflowRequest],
) (*connect.Response[workflowv1.RunWorkflowResponse], error) {
	pgID, err := uuidFromString(req.Msg.GetWorkflowId())
	if err != nil {
		return nil, connect.NewError(connect.CodeInvalidArgument, fmt.Errorf("invalid workflow_id: %w", err))
	}

	w, err := s.Queries.GetWorkflow(ctx, pgID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, connect.NewError(connect.CodeNotFound, fmt.Errorf("workflow not found"))
		}
		return nil, connect.NewError(connect.CodeInternal, err)
	}
	parsed, order, err := workflow.Parse(w.YamlSource)
	if err != nil {
		return nil, connect.NewError(connect.CodeFailedPrecondition, fmt.Errorf("stored workflow yaml is invalid: %w", err))
	}

	runID, err := uuid.NewV7()
	if err != nil {
		return nil, connect.NewError(connect.CodeInternal, err)
	}
	temporalWFID := "hf-run-" + runID.String()
	traceID := ""
	if span := trace.SpanFromContext(ctx); span.SpanContext().IsValid() {
		traceID = span.SpanContext().TraceID().String()
	}

	if _, err := s.Queries.CreateRun(ctx, store.CreateRunParams{
		ID:                 pgtype.UUID{Bytes: runID, Valid: true},
		WorkflowID:         pgID,
		TemporalWorkflowID: temporalWFID,
		Status:             "pending",
		TraceID:            traceID,
	}); err != nil {
		return nil, connect.NewError(connect.CodeInternal, fmt.Errorf("store: create run: %w", err))
	}

	_, err = s.Temporal.ExecuteWorkflow(ctx, client.StartWorkflowOptions{
		ID:        temporalWFID,
		TaskQueue: s.TaskQueue,
	}, workflow.WorkflowName, workflow.Input{
		RunID:     runID.String(),
		Workflow:  *parsed,
		Order:     order,
		RunInputs: req.Msg.GetInputs(),
	})
	if err != nil {
		_ = s.Queries.UpdateRunStatus(ctx, store.UpdateRunStatusParams{
			ID:        pgtype.UUID{Bytes: runID, Valid: true},
			Status:    "failed",
			StartedAt: pgtype.Timestamptz{},
			EndedAt:   pgtype.Timestamptz{},
			Error:     err.Error(),
		})
		return nil, connect.NewError(connect.CodeInternal, fmt.Errorf("temporal start: %w", err))
	}
	s.Log.Info("run started", "run_id", runID.String(), "workflow_id", uuidToString(pgID), "temporal_workflow_id", temporalWFID, "trace_id", traceID)
	return connect.NewResponse(&workflowv1.RunWorkflowResponse{RunId: runID.String()}), nil
}
