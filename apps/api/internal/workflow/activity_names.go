package workflow

// Stable activity names registered with Temporal. These are the wire contract
// the Python worker (apps/worker) registers against — changing them is a
// breaking change for in-flight workflows; do so via an ADR. The Go side
// only references the names here; the implementations live in
// apps/worker/harnessflow_worker/activities.
const (
	ActivityLLMCall  = "llm_call"
	ActivityRetrieve = "retrieve"
	ActivityToolCall = "tool_call"
	ActivityVerify   = "verify"
)
