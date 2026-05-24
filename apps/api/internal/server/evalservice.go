package server

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sort"

	"connectrpc.com/connect"
	"github.com/jackc/pgx/v5"

	evalv1 "github.com/rzarka1298/harnessflow/packages/sdk/gen/go/harnessflow/eval/v1"
	"github.com/rzarka1298/harnessflow/packages/sdk/gen/go/harnessflow/eval/v1/evalv1connect"

	"github.com/rzarka1298/harnessflow/apps/api/internal/store"
)

// EvalService implements evalv1connect.EvalServiceHandler. Eval *execution*
// lives in the eval-runner (apps/eval-runner), which writes results to
// Postgres; this service serves reads. RunEval is therefore unimplemented —
// trigger evals via the eval-runner CLI or the Week-8 CI gate.
type EvalService struct {
	Queries *store.Queries
}

var _ evalv1connect.EvalServiceHandler = (*EvalService)(nil)

func (s *EvalService) RunEval(
	_ context.Context,
	_ *connect.Request[evalv1.RunEvalRequest],
) (*connect.Response[evalv1.RunEvalResponse], error) {
	return nil, connect.NewError(
		connect.CodeUnimplemented,
		fmt.Errorf("eval execution runs in the eval-runner; use `harnessflow-eval` (CLI) — this API serves reads"),
	)
}

func (s *EvalService) GetEvalRun(
	ctx context.Context,
	req *connect.Request[evalv1.GetEvalRunRequest],
) (*connect.Response[evalv1.GetEvalRunResponse], error) {
	pgID, err := uuidFromString(req.Msg.GetId())
	if err != nil {
		return nil, connect.NewError(connect.CodeInvalidArgument, fmt.Errorf("invalid id: %w", err))
	}
	run, err := s.Queries.GetEvalRun(ctx, pgID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, connect.NewError(connect.CodeNotFound, fmt.Errorf("eval run not found"))
		}
		return nil, connect.NewError(connect.CodeInternal, err)
	}
	cases, err := s.Queries.ListCasesByEvalRun(ctx, pgID)
	if err != nil {
		return nil, connect.NewError(connect.CodeInternal, err)
	}
	caseResults := make([]*evalv1.EvalCaseResult, len(cases))
	for i, c := range cases {
		caseResults[i] = toProtoEvalCase(c)
	}
	return connect.NewResponse(&evalv1.GetEvalRunResponse{
		EvalRun:     toProtoEvalRun(run),
		CaseResults: caseResults,
	}), nil
}

func (s *EvalService) ListEvalRuns(
	ctx context.Context,
	req *connect.Request[evalv1.ListEvalRunsRequest],
) (*connect.Response[evalv1.ListEvalRunsResponse], error) {
	size := pageSize(req.Msg.GetPageSize())
	offset := offsetFromToken(req.Msg.GetPageToken())

	var rows []store.EvalRun
	var err error
	if req.Msg.GetWorkflowId() != "" {
		pgID, e := uuidFromString(req.Msg.GetWorkflowId())
		if e != nil {
			return nil, connect.NewError(connect.CodeInvalidArgument, fmt.Errorf("invalid workflow_id: %w", e))
		}
		rows, err = s.Queries.ListEvalRunsByWorkflow(ctx, store.ListEvalRunsByWorkflowParams{
			WorkflowID: pgID, Limit: size, Offset: offset,
		})
	} else {
		rows, err = s.Queries.ListEvalRuns(ctx, store.ListEvalRunsParams{Limit: size, Offset: offset})
	}
	if err != nil {
		return nil, connect.NewError(connect.CodeInternal, err)
	}
	out := make([]*evalv1.EvalRun, len(rows))
	for i, r := range rows {
		out[i] = toProtoEvalRun(r)
	}
	resp := &evalv1.ListEvalRunsResponse{EvalRuns: out}
	if int32(len(rows)) == size {
		resp.NextPageToken = tokenFromOffset(offset + int32(len(rows)))
	}
	return connect.NewResponse(resp), nil
}

// scoresJSONToProto turns a {scorer: score} JSONB blob into sorted
// ScorerScores (sorted so the wire order is deterministic).
func scoresJSONToProto(raw []byte) []*evalv1.ScorerScore {
	if len(raw) == 0 {
		return nil
	}
	m := map[string]float64{}
	if err := json.Unmarshal(raw, &m); err != nil {
		return nil
	}
	names := make([]string, 0, len(m))
	for k := range m {
		names = append(names, k)
	}
	sort.Strings(names)
	out := make([]*evalv1.ScorerScore, len(names))
	for i, n := range names {
		out[i] = &evalv1.ScorerScore{Scorer: n, Score: m[n]}
	}
	return out
}

func evalStatusToProto(s string) evalv1.EvalStatus {
	switch s {
	case "pending":
		return evalv1.EvalStatus_EVAL_STATUS_PENDING
	case "running":
		return evalv1.EvalStatus_EVAL_STATUS_RUNNING
	case "completed":
		return evalv1.EvalStatus_EVAL_STATUS_COMPLETED
	case "failed":
		return evalv1.EvalStatus_EVAL_STATUS_FAILED
	default:
		return evalv1.EvalStatus_EVAL_STATUS_UNSPECIFIED
	}
}

func toProtoEvalRun(r store.EvalRun) *evalv1.EvalRun {
	return &evalv1.EvalRun{
		Id:                uuidToString(r.ID),
		WorkflowId:        uuidToString(r.WorkflowID),
		Dataset:           r.Dataset,
		Status:            evalStatusToProto(r.Status),
		CreatedAt:         tsToProto(r.CreatedAt),
		CompletedAt:       tsToProto(r.CompletedAt),
		AggregateScores:   scoresJSONToProto(r.AggregateScores),
		OverallScore:      r.OverallScore,
		SeedsPerCase:      r.SeedsPerCase,
		LatencyP50Ms:      r.LatencyP50Ms,
		LatencyP95Ms:      r.LatencyP95Ms,
		CostTotalUsdCents: r.CostTotalUsdCents,
	}
}

func toProtoEvalCase(c store.EvalResultCase) *evalv1.EvalCaseResult {
	return &evalv1.EvalCaseResult{
		CaseId:        c.CaseID,
		Scores:        scoresJSONToProto(c.Scores),
		OutputPreview: c.OutputPreview,
		LatencyMs:     c.LatencyMs,
		CostUsdCents:  c.CostUsdCents,
	}
}
