// Package workflow defines the YAML→Temporal compiler and the runtime
// Workflow function that executes parsed workflows by dispatching to activities.
//
// The Workflow function (RunHarnessFlowWorkflow) is registered on a Temporal
// worker with a fixed name; activity functions are registered with the DSL
// step-type names ("llm_call", "retrieve", "tool_call", "verify"). The
// orchestrator's API process registers both; once the Python worker comes
// online (Week 3), the activity registrations move there and the Go side
// keeps only the Workflow function.
package workflow

import (
	"github.com/rzarka1298/harnessflow/packages/sdk/gen/go/schema"
)

// WorkflowName is the Temporal-registered name of the single generic
// HarnessFlow workflow function. Stable; do not change without considering
// already-running workflows in production.
const WorkflowName = "HarnessFlowWorkflow"

// TaskQueue is the Temporal task queue both the API-side worker and (Week 3+)
// the Python worker register against. Sourced from config in main.go.
const DefaultTaskQueue = "harnessflow-tasks"

// Input is the payload passed when starting a HarnessFlow workflow run.
type Input struct {
	// RunID is the orchestrator's UUID for this run, separate from Temporal's
	// own workflow id. Used for correlation in OTel and Postgres.
	RunID string `json:"run_id"`
	// Workflow is the parsed-and-validated DSL definition.
	Workflow schema.WorkflowSchemaJson `json:"workflow"`
	// Order is the topologically-sorted step name order (deterministic).
	Order []string `json:"order"`
	// RunInputs are the workflow-run parameters supplied by the caller.
	RunInputs map[string]string `json:"run_inputs"`
}

// Output is the result of a completed run, returned to anyone awaiting the
// Temporal workflow's completion.
type Output struct {
	StepOutputs       map[string]ActivityResult `json:"step_outputs"`
	TotalInputTokens  int64                     `json:"total_input_tokens"`
	TotalOutputTokens int64                     `json:"total_output_tokens"`
	TotalCostUsdCents int64                     `json:"total_cost_usd_cents"`
}

// ActivityInput is the shape every activity receives. Each activity reads
// only the fields relevant to its step type; cross-field validation happens
// before the workflow starts (in the parser/compiler).
type ActivityInput struct {
	RunID        string                    `json:"run_id"`
	WorkflowName string                    `json:"workflow_name"`
	StepName     string                    `json:"step_name"`
	Step         schema.Step               `json:"step"`
	RunInputs    map[string]string         `json:"run_inputs"`
	PriorOutputs map[string]ActivityResult `json:"prior_outputs"`
}

// RunStatusInput is the payload for the record_run_status activity, which
// persists a run's lifecycle transitions and emits run-level metrics. It is
// not a DSL step — the workflow calls it at start ("running") and on
// completion/failure.
type RunStatusInput struct {
	RunID           string `json:"run_id"`
	WorkflowName    string `json:"workflow_name"`
	WorkflowVersion int32  `json:"workflow_version"`
	// Status is one of: running, completed, failed.
	Status string `json:"status"`
	Error  string `json:"error"`
}

// ActivityResult is the shape every activity returns.
type ActivityResult struct {
	Output       string `json:"output"`
	InputTokens  int64  `json:"input_tokens"`
	OutputTokens int64  `json:"output_tokens"`
	CostUsdCents int64  `json:"cost_usd_cents"`
}
