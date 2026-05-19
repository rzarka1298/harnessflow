package workflow

import (
	"context"
	"fmt"
	"time"

	"go.temporal.io/sdk/activity"
)

// Stable activity names registered with Temporal. These map 1:1 to the DSL
// step `type` values — the compiler dispatches by name via
// `workflow.ExecuteActivity(ctx, ActivityName, ...)`. Changing these is a
// breaking change for in-flight workflows; do so via an ADR.
const (
	ActivityLLMCall  = "llm_call"
	ActivityRetrieve = "retrieve"
	ActivityToolCall = "tool_call"
	ActivityVerify   = "verify"
)

// stubActivities holds the Week 2 placeholder implementations. Week 3 swaps in
// the real Python workers (registering the same activity names on the same
// task queue); the Go-side stubs are deleted at that point.

// LLMCallStub fakes an LLM call by sleeping briefly and returning a canned
// output. Replaced by harnessflow_worker.activities.llm_call in Week 3.
func LLMCallStub(ctx context.Context, in ActivityInput) (ActivityResult, error) {
	logStubStart(ctx, in)
	time.Sleep(150 * time.Millisecond)
	model := ""
	if in.Step.Model != nil {
		model = *in.Step.Model
	}
	return ActivityResult{
		Output:       fmt.Sprintf("stub-llm-output(step=%s, model=%s)", in.StepName, model),
		InputTokens:  42,
		OutputTokens: 21,
		CostUsdCents: 1,
	}, nil
}

// RetrieveStub fakes a vector retrieval.
func RetrieveStub(ctx context.Context, in ActivityInput) (ActivityResult, error) {
	logStubStart(ctx, in)
	time.Sleep(80 * time.Millisecond)
	source := ""
	if in.Step.Source != nil {
		source = *in.Step.Source
	}
	return ActivityResult{
		Output: fmt.Sprintf("stub-retrieve-output(step=%s, source=%s, top_k=%d)",
			in.StepName, source, in.Step.TopK),
	}, nil
}

// ToolCallStub fakes a tool execution.
func ToolCallStub(ctx context.Context, in ActivityInput) (ActivityResult, error) {
	logStubStart(ctx, in)
	time.Sleep(60 * time.Millisecond)
	return ActivityResult{
		Output: fmt.Sprintf("stub-tool-output(step=%s, tools=%v)", in.StepName, in.Step.Tools),
	}, nil
}

// VerifyStub fakes a verifier loop result.
func VerifyStub(ctx context.Context, in ActivityInput) (ActivityResult, error) {
	logStubStart(ctx, in)
	time.Sleep(40 * time.Millisecond)
	return ActivityResult{
		Output: fmt.Sprintf("stub-verify-output(step=%s, ok=true)", in.StepName),
	}, nil
}

func logStubStart(ctx context.Context, in ActivityInput) {
	activity.GetLogger(ctx).Info("stub activity",
		"step", in.StepName,
		"type", string(in.Step.Type),
		"run_id", in.RunID,
	)
}
