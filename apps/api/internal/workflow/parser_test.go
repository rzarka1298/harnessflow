package workflow

import (
	"strings"
	"testing"
)

const minimalYAML = `
name: research-assistant
version: 1
steps:
  planner:
    type: llm_call
    model: gpt-4o
    prompt: |
      Break the question into sub-queries.
  retriever:
    type: retrieve
    source: vector-db
    after: [planner]
  executor:
    type: llm_call
    model: gpt-4o
    prompt: |
      Answer using the context.
    after: [retriever]
  verifier:
    type: verify
    after: [executor]
`

func TestParse_HappyPath(t *testing.T) {
	wf, order, err := Parse(minimalYAML)
	if err != nil {
		t.Fatalf("Parse: %v", err)
	}
	if wf.Name != "research-assistant" {
		t.Fatalf("name: got %q want research-assistant", wf.Name)
	}
	if len(wf.Steps) != 4 {
		t.Fatalf("steps: got %d want 4", len(wf.Steps))
	}

	// planner must come first; verifier last.
	if order[0] != "planner" {
		t.Errorf("topo first: got %q want planner", order[0])
	}
	if order[len(order)-1] != "verifier" {
		t.Errorf("topo last: got %q want verifier", order[len(order)-1])
	}

	// retriever must come before executor; executor before verifier.
	pos := map[string]int{}
	for i, n := range order {
		pos[n] = i
	}
	if pos["retriever"] >= pos["executor"] {
		t.Errorf("retriever must precede executor: order=%v", order)
	}
	if pos["executor"] >= pos["verifier"] {
		t.Errorf("executor must precede verifier: order=%v", order)
	}
}

func TestParse_DeterministicOrder(t *testing.T) {
	// Two independent root steps + one common child — topo sort must break
	// ties alphabetically so the order is identical across runs.
	yamlSrc := `
name: parallel
version: 1
steps:
  zulu:
    type: llm_call
    model: gpt-4o
    prompt: "first"
  alpha:
    type: llm_call
    model: gpt-4o
    prompt: "second"
  joiner:
    type: verify
    after: [zulu, alpha]
`
	_, order, err := Parse(yamlSrc)
	if err != nil {
		t.Fatalf("Parse: %v", err)
	}
	want := []string{"alpha", "zulu", "joiner"}
	if len(order) != len(want) {
		t.Fatalf("order length: got %v want %v", order, want)
	}
	for i, n := range want {
		if order[i] != n {
			t.Fatalf("order[%d]: got %q want %q (full: %v)", i, order[i], n, order)
		}
	}
}

func TestParse_RejectsCycle(t *testing.T) {
	yamlSrc := `
name: cyclic
version: 1
steps:
  a:
    type: verify
    after: [b]
  b:
    type: verify
    after: [a]
`
	_, _, err := Parse(yamlSrc)
	if err == nil {
		t.Fatal("expected cycle error, got nil")
	}
	if !strings.Contains(err.Error(), "cycle") {
		t.Errorf("expected error mentioning cycle, got: %v", err)
	}
}

func TestParse_RejectsUnknownAfter(t *testing.T) {
	yamlSrc := `
name: bad-after
version: 1
steps:
  a:
    type: verify
    after: [nonexistent]
`
	_, _, err := Parse(yamlSrc)
	if err == nil {
		t.Fatal("expected unknown-step error, got nil")
	}
	if !strings.Contains(err.Error(), "nonexistent") {
		t.Errorf("expected error mentioning the bad step, got: %v", err)
	}
}

func TestParse_RejectsLLMCallWithoutModel(t *testing.T) {
	yamlSrc := `
name: no-model
version: 1
steps:
  a:
    type: llm_call
    prompt: hi
`
	_, _, err := Parse(yamlSrc)
	if err == nil {
		t.Fatal("expected missing-model error, got nil")
	}
	if !strings.Contains(err.Error(), "model") {
		t.Errorf("expected error mentioning model, got: %v", err)
	}
}

func TestParse_RejectsEmptyYAML(t *testing.T) {
	_, _, err := Parse("")
	if err == nil {
		t.Fatal("expected empty-source error, got nil")
	}
}
