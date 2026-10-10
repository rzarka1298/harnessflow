package workflow

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/mock"
	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/testsuite"
	temporalworkflow "go.temporal.io/sdk/workflow"
)

func TestProjectWorkflowRepairsUntilCompleted(t *testing.T) {
	var suite testsuite.WorkflowTestSuite
	env := suite.NewTestWorkflowEnvironment()
	env.RegisterActivityWithOptions(func(context.Context, ProjectInput) (ProjectTickResult, error) { return ProjectTickResult{}, nil }, activity.RegisterOptions{Name: "project_tick"})
	env.OnActivity("project_tick", mock.Anything, ProjectInput{RunID: "run"}).Return(ProjectTickResult{Status: "verifying"}, nil).Once()
	env.OnActivity("project_tick", mock.Anything, ProjectInput{RunID: "run"}).Return(ProjectTickResult{Status: "running"}, nil).Once()
	env.OnActivity("project_tick", mock.Anything, ProjectInput{RunID: "run"}).Return(ProjectTickResult{Status: "completed"}, nil).Once()
	env.ExecuteWorkflow(ProjectWorkflow, ProjectInput{RunID: "run"})
	if err := env.GetWorkflowError(); err != nil {
		t.Fatal(err)
	}
	env.AssertExpectations(t)
}

func TestProjectWorkflowBoundsHistory(t *testing.T) {
	var suite testsuite.WorkflowTestSuite
	env := suite.NewTestWorkflowEnvironment()
	env.RegisterWorkflowWithOptions(ProjectWorkflow, temporalworkflow.RegisterOptions{Name: ProjectWorkflowName})
	env.RegisterActivityWithOptions(func(context.Context, ProjectInput) (ProjectTickResult, error) { return ProjectTickResult{}, nil }, activity.RegisterOptions{Name: "project_tick"})
	env.OnActivity("project_tick", mock.Anything, mock.Anything).Return(ProjectTickResult{Status: "running"}, nil).Times(100)
	env.ExecuteWorkflow(ProjectWorkflowName, ProjectInput{RunID: "run"})
	if !temporalworkflow.IsContinueAsNewError(env.GetWorkflowError()) {
		t.Fatalf("expected history continuation, got %v", env.GetWorkflowError())
	}
	env.AssertExpectations(t)
}
func TestProjectWorkflowWaitsForControl(t *testing.T) {
	for _, status := range []string{"paused", "blocked", "exhausted"} {
		t.Run(status, func(t *testing.T) {
			var suite testsuite.WorkflowTestSuite
			env := suite.NewTestWorkflowEnvironment()
			env.RegisterActivityWithOptions(func(context.Context, ProjectInput) (ProjectTickResult, error) { return ProjectTickResult{}, nil }, activity.RegisterOptions{Name: "project_tick"})
			env.OnActivity("project_tick", mock.Anything, mock.Anything).Return(ProjectTickResult{Status: status}, nil).Once()
			env.OnActivity("project_tick", mock.Anything, mock.Anything).Return(ProjectTickResult{Status: "canceled"}, nil).Once()
			env.RegisterDelayedCallback(func() { env.SignalWorkflow(ProjectControlSignal, "cancel") }, time.Hour)
			start := env.Now()
			env.ExecuteWorkflow(ProjectWorkflow, ProjectInput{RunID: "run"})
			if err := env.GetWorkflowError(); err != nil {
				t.Fatal(err)
			}
			if env.Now().Sub(start) < time.Hour {
				t.Fatal("did not wait for control")
			}
			env.AssertExpectations(t)
		})
	}
}
