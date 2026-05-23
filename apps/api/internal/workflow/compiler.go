package workflow

import (
	"fmt"
	"time"

	"github.com/rzarka1298/harnessflow/packages/sdk/gen/go/schema"
	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

// HarnessFlowWorkflow is the single, generic Temporal workflow function that
// executes any HarnessFlow YAML workflow at runtime by interpreting the parsed
// IR. Registered under WorkflowName.
//
// It brackets the step execution with record_run_status activities so the
// run's terminal state is persisted to Postgres and run-level metrics are
// emitted, regardless of success or failure.
//
// Determinism contract: this function MUST be deterministic — it relies on the
// pre-computed Input.Order (deterministic, computed by Parse), and never
// iterates wf.Steps as a map. All I/O happens in activities.
func HarnessFlowWorkflow(ctx workflow.Context, in Input) (Output, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("workflow start",
		"run_id", in.RunID,
		"name", in.Workflow.Name,
		"version", in.Workflow.Version,
		"steps", len(in.Workflow.Steps),
	)

	recordStatus(ctx, in, "running", "")

	out, err := runSteps(ctx, in)
	if err != nil {
		recordStatus(ctx, in, "failed", err.Error())
		return out, err
	}

	recordStatus(ctx, in, "completed", "")
	logger.Info("workflow complete",
		"run_id", in.RunID,
		"total_cost_cents", out.TotalCostUsdCents,
		"total_tokens", out.TotalInputTokens+out.TotalOutputTokens,
	)
	return out, nil
}

// runSteps executes the workflow's activities in topological order, threading
// each step's output to downstream steps.
func runSteps(ctx workflow.Context, in Input) (Output, error) {
	logger := workflow.GetLogger(ctx)
	out := Output{
		StepOutputs: make(map[string]ActivityResult, len(in.Workflow.Steps)),
	}

	for _, name := range in.Order {
		step := in.Workflow.Steps[name]

		// Human approval gate: pause until an approve signal arrives. The run
		// is marked waiting_approval so the dashboard can surface an Approve
		// button; on signal we flip back to running and proceed.
		if step.RequiresApproval {
			recordStatus(ctx, in, "waiting_approval", "")
			logger.Info("waiting for approval", "step", name)
			var sig ApprovalSignal
			workflow.GetSignalChannel(ctx, SignalApprove).Receive(ctx, &sig)
			logger.Info("approval received", "step", name, "approved_by", sig.ApprovedBy)
			recordStatus(ctx, in, "running", "")
		}

		ctxStep := workflow.WithActivityOptions(ctx, activityOptionsFor(step))
		actInput := ActivityInput{
			RunID:        in.RunID,
			WorkflowName: in.Workflow.Name,
			StepName:     name,
			Step:         step,
			RunInputs:    in.RunInputs,
			PriorOutputs: out.StepOutputs,
		}

		actName, err := activityNameFor(step.Type)
		if err != nil {
			return out, err
		}

		var result ActivityResult
		future := workflow.ExecuteActivity(ctxStep, actName, actInput)
		if err := future.Get(ctxStep, &result); err != nil {
			logger.Error("step failed", "step", name, "error", err)
			return out, fmt.Errorf("step %q failed: %w", name, err)
		}

		out.StepOutputs[name] = result
		out.TotalInputTokens += result.InputTokens
		out.TotalOutputTokens += result.OutputTokens
		out.TotalCostUsdCents += result.CostUsdCents
	}
	return out, nil
}

// recordStatus invokes the record_run_status activity best-effort: a failure to
// persist status must not change the workflow's own success/failure outcome, so
// the error is logged and swallowed. A short timeout keeps a stuck status write
// from stalling the run.
func recordStatus(ctx workflow.Context, in Input, status, errMsg string) {
	ctxStatus := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:    time.Second,
			BackoffCoefficient: 2,
			MaximumAttempts:    3,
		},
	})
	input := RunStatusInput{
		RunID:           in.RunID,
		WorkflowName:    in.Workflow.Name,
		WorkflowVersion: int32(in.Workflow.Version),
		Status:          status,
		Error:           errMsg,
	}
	if err := workflow.ExecuteActivity(ctxStatus, ActivityRecordRunStatus, input).Get(ctxStatus, nil); err != nil {
		workflow.GetLogger(ctx).Warn("record_run_status failed", "status", status, "error", err)
	}
}

// activityNameFor maps a DSL step type to the registered Temporal activity.
func activityNameFor(t schema.StepType) (string, error) {
	switch t {
	case schema.StepTypeLlmCall:
		return ActivityLLMCall, nil
	case schema.StepTypeRetrieve:
		return ActivityRetrieve, nil
	case schema.StepTypeToolCall:
		return ActivityToolCall, nil
	case schema.StepTypeVerify:
		return ActivityVerify, nil
	default:
		return "", fmt.Errorf("compiler: unknown step type %q", t)
	}
}

// activityOptionsFor derives Temporal ActivityOptions from a parsed step,
// applying retry-policy defaults from the DSL.
func activityOptionsFor(step schema.Step) workflow.ActivityOptions {
	opts := workflow.ActivityOptions{
		StartToCloseTimeout: 5 * time.Minute,
	}
	maxAttempts := int32(3)
	if step.RetryPolicy != nil && step.RetryPolicy.MaxAttempts > 0 {
		maxAttempts = int32(step.RetryPolicy.MaxAttempts)
	}
	opts.RetryPolicy = &temporal.RetryPolicy{
		InitialInterval:    time.Second,
		BackoffCoefficient: 2,
		MaximumAttempts:    maxAttempts,
	}
	return opts
}
