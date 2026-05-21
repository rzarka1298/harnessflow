#!/usr/bin/env bash
# scripts/demo.sh — end-to-end demo runner for the HarnessFlow research-assistant
# workflow. Invoked by `make demo`.
#
# Expects the docker-compose stack to be up (`make up`). Brings up the Go API
# and Python worker as host processes, seeds ChromaDB if needed, creates the
# workflow, runs it, prints the result. Leaves the api/worker running so the
# dashboard (`pnpm dev`) can browse the run.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PIDS_FILE="/tmp/harnessflow_demo.pids"
API_LOG="/tmp/harnessflow_demo_api.log"
WORKER_LOG="/tmp/harnessflow_demo_worker.log"

API_PORT="${API_PORT:-8080}"
QUERY="${HARNESSFLOW_QUERY:-How does Temporal handle workflow retries vs activity retries?}"

# --- preflight ---------------------------------------------------------------
need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1" >&2; exit 1; }; }
need docker
need jq
need curl
need go

if ! docker compose ps --status running --services 2>/dev/null | grep -q postgres; then
    echo "docker-compose stack not up. Run \`make up\` first." >&2
    exit 1
fi

# --- seed corpus once --------------------------------------------------------
if [ ! -d "$REPO_ROOT/apps/worker/data/chroma" ]; then
    echo ">> seeding ChromaDB"
    ( cd "$REPO_ROOT/apps/worker" && uv run python "$REPO_ROOT/scripts/seed-chroma.py" )
fi

# --- start api + worker if not already running -------------------------------
start_api() {
    if curl -sf "http://localhost:${API_PORT}/healthz" >/dev/null 2>&1; then
        echo ">> api already up"
        return
    fi
    echo ">> starting api"
    ( cd "$REPO_ROOT/apps/api" && go run ./cmd/api ) > "$API_LOG" 2>&1 &
    echo "$!" >> "$PIDS_FILE"
    until grep -q "http server listening" "$API_LOG" 2>/dev/null; do sleep 1; done
}

start_worker() {
    if pgrep -f harnessflow_worker >/dev/null 2>&1; then
        echo ">> worker already up"
        return
    fi
    echo ">> starting worker"
    ( cd "$REPO_ROOT/apps/worker" && .venv/bin/python -m harnessflow_worker ) > "$WORKER_LOG" 2>&1 &
    echo "$!" >> "$PIDS_FILE"
    until grep -q "worker started" "$WORKER_LOG" 2>/dev/null; do sleep 1; done
}

: > "$PIDS_FILE"
start_api
start_worker

# --- create + run the workflow ----------------------------------------------
YAML="$(cat "$REPO_ROOT/packages/examples/workflows/research-assistant.yaml")"

WFID=$(curl -sf -X POST "http://localhost:${API_PORT}/harnessflow.workflow.v1.WorkflowService/CreateWorkflow" \
    -H 'Content-Type: application/json' \
    -d "$(jq -n --arg y "$YAML" '{yaml_source:$y}')" | jq -r '.workflow.id')
echo ">> workflow created: $WFID"

RUNID=$(curl -sf -X POST "http://localhost:${API_PORT}/harnessflow.workflow.v1.WorkflowService/RunWorkflow" \
    -H 'Content-Type: application/json' \
    -d "$(jq -n --arg wf "$WFID" --arg q "$QUERY" '{workflow_id:$wf, inputs:{query:$q}}')" \
    | jq -r '.runId')
echo ">> run started:      $RUNID"

# --- wait for completion ----------------------------------------------------
while :; do
    st=$(docker exec harnessflow-temporal-1 temporal workflow describe \
        --workflow-id "hf-run-$RUNID" --address temporal:7233 -o json 2>/dev/null \
        | jq -r '.workflowExecutionInfo.status' 2>/dev/null)
    case "$st" in
        WORKFLOW_EXECUTION_STATUS_COMPLETED) echo ">> temporal: COMPLETED"; break;;
        WORKFLOW_EXECUTION_STATUS_FAILED) echo ">> temporal: FAILED" >&2; exit 1;;
    esac
    sleep 1
done

# --- summarize ---------------------------------------------------------------
echo
echo "=== workflow_steps ==="
docker exec harnessflow-postgres-1 psql -U harnessflow -d harnessflow -c \
    "SELECT name, type, status, latency_ms, input_tokens, output_tokens, cost_usd_cents FROM workflow_steps WHERE run_id = '$RUNID' ORDER BY started_at;"

TRACE_ID=$(curl -sf -X POST "http://localhost:${API_PORT}/harnessflow.run.v1.RunService/GetRun" \
    -H 'Content-Type: application/json' -d "{\"id\":\"$RUNID\"}" | jq -r '.run.traceId')
echo
echo ">> view in dashboard:  http://localhost:3000/runs/$RUNID"
echo ">> view in Jaeger:     http://localhost:16686/trace/$TRACE_ID"
echo
echo ">> demo complete. api+worker still running. Stop with: pkill -f harnessflow_worker; lsof -ti :8080 | xargs kill"
