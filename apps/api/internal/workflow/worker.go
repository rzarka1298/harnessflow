package workflow

import (
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/interceptor"
	"go.temporal.io/sdk/worker"
	tworkflow "go.temporal.io/sdk/workflow"
)

// NewWorker constructs (but does not start) a Temporal worker that registers
// the HarnessFlow Workflow function only. Activity execution lives in the
// Python worker process (apps/worker) — both register against the same task
// queue and Temporal routes by task type. Start it with w.Run().
//
// The optional interceptors slice is forwarded to worker.Options — pass the
// OTel tracing interceptor here so workflow spans hang off the inbound RPC
// trace.
func NewWorker(tc client.Client, taskQueue string, interceptors []interceptor.WorkerInterceptor) worker.Worker {
	w := worker.New(tc, taskQueue, worker.Options{
		Interceptors: interceptors,
		// This worker registers ONLY the workflow function — activity
		// implementations live in the Python worker. Without this flag the
		// Go worker would still long-poll for activity tasks and reject
		// them with ActivityNotRegisteredError, racing the Python worker.
		LocalActivityWorkerOnly: true,
	})

	w.RegisterWorkflowWithOptions(HarnessFlowWorkflow, tworkflow.RegisterOptions{
		Name: WorkflowName,
	})

	return w
}
