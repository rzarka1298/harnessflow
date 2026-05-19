// conv.go: lossless conversions between sqlc-generated store rows and the
// protobuf-generated wire types.
package server

import (
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgtype"
	"google.golang.org/protobuf/types/known/timestamppb"

	runv1 "github.com/rzarka1298/harnessflow/packages/sdk/gen/go/harnessflow/run/v1"
	workflowv1 "github.com/rzarka1298/harnessflow/packages/sdk/gen/go/harnessflow/workflow/v1"
	"github.com/rzarka1298/harnessflow/apps/api/internal/store"
)

func uuidToString(u pgtype.UUID) string {
	if !u.Valid {
		return ""
	}
	return uuid.UUID(u.Bytes).String()
}

func uuidFromString(s string) (pgtype.UUID, error) {
	parsed, err := uuid.Parse(s)
	if err != nil {
		return pgtype.UUID{}, err
	}
	return pgtype.UUID{Bytes: parsed, Valid: true}, nil
}

func tsToProto(ts pgtype.Timestamptz) *timestamppb.Timestamp {
	if !ts.Valid {
		return nil
	}
	return timestamppb.New(ts.Time)
}

func workflowStatusToProto(s string) workflowv1.WorkflowStatus {
	switch s {
	case "draft":
		return workflowv1.WorkflowStatus_WORKFLOW_STATUS_DRAFT
	case "active":
		return workflowv1.WorkflowStatus_WORKFLOW_STATUS_ACTIVE
	case "archived":
		return workflowv1.WorkflowStatus_WORKFLOW_STATUS_ARCHIVED
	default:
		return workflowv1.WorkflowStatus_WORKFLOW_STATUS_UNSPECIFIED
	}
}

func runStatusToProto(s string) runv1.RunStatus {
	switch s {
	case "pending":
		return runv1.RunStatus_RUN_STATUS_PENDING
	case "running":
		return runv1.RunStatus_RUN_STATUS_RUNNING
	case "completed":
		return runv1.RunStatus_RUN_STATUS_COMPLETED
	case "failed":
		return runv1.RunStatus_RUN_STATUS_FAILED
	case "waiting_approval":
		return runv1.RunStatus_RUN_STATUS_WAITING_APPROVAL
	case "canceled":
		return runv1.RunStatus_RUN_STATUS_CANCELED
	default:
		return runv1.RunStatus_RUN_STATUS_UNSPECIFIED
	}
}

func stepStatusToProto(s string) runv1.StepStatus {
	switch s {
	case "pending":
		return runv1.StepStatus_STEP_STATUS_PENDING
	case "running":
		return runv1.StepStatus_STEP_STATUS_RUNNING
	case "completed":
		return runv1.StepStatus_STEP_STATUS_COMPLETED
	case "failed":
		return runv1.StepStatus_STEP_STATUS_FAILED
	case "skipped":
		return runv1.StepStatus_STEP_STATUS_SKIPPED
	default:
		return runv1.StepStatus_STEP_STATUS_UNSPECIFIED
	}
}

func toProtoWorkflow(w store.Workflow) *workflowv1.Workflow {
	return &workflowv1.Workflow{
		Id:          uuidToString(w.ID),
		Name:        w.Name,
		Version:     w.Version,
		Description: w.Description,
		YamlSource:  w.YamlSource,
		Status:      workflowStatusToProto(w.Status),
		CreatedAt:   tsToProto(w.CreatedAt),
		UpdatedAt:   tsToProto(w.UpdatedAt),
	}
}

func toProtoRun(r store.WorkflowRun) *runv1.Run {
	return &runv1.Run{
		Id:                uuidToString(r.ID),
		WorkflowId:        uuidToString(r.WorkflowID),
		Status:            runStatusToProto(r.Status),
		StartedAt:         tsToProto(r.StartedAt),
		EndedAt:           tsToProto(r.EndedAt),
		TotalCostUsdCents: r.TotalCostUsdCents,
		TotalTokens:       r.TotalTokens,
		TraceId:           r.TraceID,
	}
}

func toProtoStep(s store.WorkflowStep) *runv1.Step {
	return &runv1.Step{
		Id:           uuidToString(s.ID),
		RunId:        uuidToString(s.RunID),
		Name:         s.Name,
		Type:         s.Type,
		Status:       stepStatusToProto(s.Status),
		StartedAt:    tsToProto(s.StartedAt),
		EndedAt:      tsToProto(s.EndedAt),
		LatencyMs:    s.LatencyMs,
		InputTokens:  s.InputTokens,
		OutputTokens: s.OutputTokens,
		CostUsdCents: s.CostUsdCents,
		Attempt:      s.Attempt,
		Error:        s.Error,
	}
}
