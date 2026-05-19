package workflow

import (
	"fmt"
	"sort"

	"github.com/rzarka1298/harnessflow/packages/sdk/gen/go/schema"
	"sigs.k8s.io/yaml"
)

// Parse converts workflow YAML into a validated schema struct plus a
// deterministic topological step ordering. Validation includes the JSON-schema
// constraints baked into the generated UnmarshalJSON, plus DAG cycle/reference
// checks performed here.
func Parse(yamlSource string) (*schema.WorkflowSchemaJson, []string, error) {
	if yamlSource == "" {
		return nil, nil, fmt.Errorf("workflow: yaml source is empty")
	}
	var wf schema.WorkflowSchemaJson
	// sigs.k8s.io/yaml converts YAML → JSON before unmarshalling, so the
	// generated UnmarshalJSON validation runs.
	if err := yaml.Unmarshal([]byte(yamlSource), &wf); err != nil {
		return nil, nil, fmt.Errorf("workflow: parse yaml: %w", err)
	}
	order, err := topoSort(&wf)
	if err != nil {
		return nil, nil, err
	}
	if err := validateCrossField(&wf); err != nil {
		return nil, nil, err
	}
	return &wf, order, nil
}

// topoSort returns step names in dependency order using Kahn's algorithm.
// Ties are broken alphabetically to keep the ordering deterministic — Temporal
// workflows MUST be deterministic.
func topoSort(wf *schema.WorkflowSchemaJson) ([]string, error) {
	incoming := make(map[string]int, len(wf.Steps))
	edges := make(map[string][]string, len(wf.Steps))
	for name := range wf.Steps {
		incoming[name] = 0
	}
	for name, step := range wf.Steps {
		for _, dep := range step.After {
			if _, ok := wf.Steps[dep]; !ok {
				return nil, fmt.Errorf("workflow: step %q references unknown step %q in 'after'", name, dep)
			}
			edges[dep] = append(edges[dep], name)
			incoming[name]++
		}
	}
	// Sort the children of each node so the BFS pops them in a stable order.
	for k := range edges {
		sort.Strings(edges[k])
	}

	ready := make([]string, 0, len(wf.Steps))
	for name, deg := range incoming {
		if deg == 0 {
			ready = append(ready, name)
		}
	}
	sort.Strings(ready)

	order := make([]string, 0, len(wf.Steps))
	for len(ready) > 0 {
		next := ready[0]
		ready = ready[1:]
		order = append(order, next)
		for _, child := range edges[next] {
			incoming[child]--
			if incoming[child] == 0 {
				ready = append(ready, child)
			}
		}
		sort.Strings(ready)
	}
	if len(order) != len(wf.Steps) {
		return nil, fmt.Errorf("workflow: dependency cycle in steps")
	}
	return order, nil
}

// validateCrossField enforces type-specific required fields that the JSON
// schema (intentionally) leaves to the compiler. See packages/workflow-dsl/SPEC.md.
func validateCrossField(wf *schema.WorkflowSchemaJson) error {
	for name, step := range wf.Steps {
		switch step.Type {
		case schema.StepTypeLlmCall:
			if step.Model == nil || *step.Model == "" {
				return fmt.Errorf("workflow: step %q (llm_call): 'model' is required", name)
			}
			if step.Prompt == nil || *step.Prompt == "" {
				return fmt.Errorf("workflow: step %q (llm_call): 'prompt' is required", name)
			}
		case schema.StepTypeRetrieve:
			if step.Source == nil || *step.Source == "" {
				return fmt.Errorf("workflow: step %q (retrieve): 'source' is required", name)
			}
		case schema.StepTypeToolCall:
			if len(step.Tools) == 0 {
				return fmt.Errorf("workflow: step %q (tool_call): 'tools' must be non-empty", name)
			}
		case schema.StepTypeVerify:
			// criteria is optional for now.
		default:
			return fmt.Errorf("workflow: step %q: unknown type %q", name, step.Type)
		}
	}
	return nil
}
