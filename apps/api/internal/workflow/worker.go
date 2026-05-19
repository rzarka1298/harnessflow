package workflow

import (
	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"
	tworkflow "go.temporal.io/sdk/workflow"
)

// NewWorker constructs (but does not start) a Temporal worker registered with
// the HarnessFlow workflow and Week-2 stub activities. Start it with w.Run().
//
// In Week 3 the activity registrations move to the Python worker; this
// constructor will then register only the Workflow function.
func NewWorker(tc client.Client, taskQueue string) worker.Worker {
	w := worker.New(tc, taskQueue, worker.Options{})

	w.RegisterWorkflowWithOptions(HarnessFlowWorkflow, tworkflow.RegisterOptions{
		Name: WorkflowName,
	})

	w.RegisterActivityWithOptions(LLMCallStub, activity.RegisterOptions{Name: ActivityLLMCall})
	w.RegisterActivityWithOptions(RetrieveStub, activity.RegisterOptions{Name: ActivityRetrieve})
	w.RegisterActivityWithOptions(ToolCallStub, activity.RegisterOptions{Name: ActivityToolCall})
	w.RegisterActivityWithOptions(VerifyStub, activity.RegisterOptions{Name: ActivityVerify})

	return w
}
