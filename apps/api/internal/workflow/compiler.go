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

	out := Output{
		StepOutputs: make(map[string]ActivityResult, len(in.Workflow.Steps)),
	}

	for _, name := range in.Order {
		step := in.Workflow.Steps[name]

		ctxStep := workflow.WithActivityOptions(ctx, activityOptionsFor(step))
		actInput := ActivityInput{
			RunID:        in.RunID,
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

	logger.Info("workflow complete",
		"run_id", in.RunID,
		"total_cost_cents", out.TotalCostUsdCents,
		"total_tokens", out.TotalInputTokens+out.TotalOutputTokens,
	)
	return out, nil
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
