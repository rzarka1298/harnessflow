-- name: CreateRun :one
INSERT INTO workflow_runs (id, workflow_id, temporal_workflow_id, status, trace_id)
VALUES ($1, $2, $3, $4, $5)
RETURNING *;

-- name: GetRun :one
SELECT * FROM workflow_runs WHERE id = $1;

-- name: ListRuns :many
SELECT * FROM workflow_runs
ORDER BY created_at DESC, id DESC
LIMIT $1 OFFSET $2;

-- name: ListRunsByWorkflow :many
SELECT * FROM workflow_runs
WHERE workflow_id = $1
ORDER BY created_at DESC, id DESC
LIMIT $2 OFFSET $3;

-- name: UpdateRunStatus :exec
UPDATE workflow_runs
SET status = $2,
    started_at = COALESCE(started_at, $3),
    ended_at = $4,
    error = $5
WHERE id = $1;

-- name: ListStepsByRun :many
SELECT * FROM workflow_steps
WHERE run_id = $1
ORDER BY created_at ASC, id ASC;

-- name: CreateStep :one
INSERT INTO workflow_steps (id, run_id, name, type, status)
VALUES ($1, $2, $3, $4, $5)
RETURNING *;

-- name: UpdateStepStatus :exec
UPDATE workflow_steps
SET status = $2,
    started_at = COALESCE(started_at, $3),
    ended_at = $4,
    latency_ms = $5,
    error = $6
WHERE id = $1;
