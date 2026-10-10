package workflow

import (
	"fmt"
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

// ProjectWorkflowName is the durable registered coding-run workflow name.
const ProjectWorkflowName = "HarnessFlowProjectRun"

// ProjectControlSignal wakes a project workflow to consume stored controls.
const ProjectControlSignal = "project_control"

// ProjectInput identifies the durable worker-owned project state.
type ProjectInput struct {
	RunID string `json:"run_id"`
}

// ProjectTickResult reports the next scheduling state from the worker.
type ProjectTickResult struct {
	Status string `json:"status"`
	Reason string `json:"reason"`
}

// ProjectWorkflow keeps the durable scheduling history separate from the
// worker's versioned project state. Activities must fence concurrent retries.
func ProjectWorkflow(ctx workflow.Context, in ProjectInput) error {
	ctx = workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: time.Hour, HeartbeatTimeout: 15 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{InitialInterval: time.Second, MaximumInterval: time.Minute, MaximumAttempts: 0},
	})
	signals := workflow.GetSignalChannel(ctx, ProjectControlSignal)
	for tick := 0; tick < 100; tick++ {
		// Signals are wake hints only. Commands are durable in Postgres, so
		// discard stale hints before reading state through the next activity.
		var pendingSignal string
		for signals.ReceiveAsync(&pendingSignal) {
		}
		var result ProjectTickResult
		if err := workflow.ExecuteActivity(ctx, "project_tick", in).Get(ctx, &result); err != nil {
			return err
		}
		switch result.Status {
		case "completed", "failed", "canceled":
			return nil
		case "paused", "blocked", "exhausted":
			var signal string
			signals.Receive(ctx, &signal)
		case "queued", "running", "planning", "executing", "verifying":
			// A retry may find a still-live repository owner. Back off instead of
			// filling Temporal history while waiting for its watchdog to exit.
			if result.Status == "running" && result.Reason != "" && workflow.GetVersion(ctx, "project-contention-backoff", workflow.DefaultVersion, 1) >= 1 {
				if err := workflow.Sleep(ctx, time.Second); err != nil {
					return err
				}
			}
		default:
			return fmt.Errorf("project_tick returned unknown status %q", result.Status)
		}
	}
	return workflow.NewContinueAsNewError(ctx, ProjectWorkflowName, in)
}
