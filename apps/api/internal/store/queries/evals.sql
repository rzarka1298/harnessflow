-- name: CreateEvalRun :one
INSERT INTO eval_runs (
    id, workflow_id, dataset, status, seeds_per_case, overall_score,
    aggregate_scores, latency_p50_ms, latency_p95_ms, cost_total_usd_cents,
    completed_at
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
RETURNING *;

-- name: CreateEvalCase :one
INSERT INTO eval_result_cases (
    id, eval_run_id, case_id, scores, output_preview, latency_ms, cost_usd_cents
)
VALUES ($1, $2, $3, $4, $5, $6, $7)
RETURNING *;

-- name: GetEvalRun :one
SELECT * FROM eval_runs WHERE id = $1;

-- name: ListEvalRuns :many
SELECT * FROM eval_runs
ORDER BY created_at DESC, id DESC
LIMIT $1 OFFSET $2;

-- name: ListEvalRunsByWorkflow :many
SELECT * FROM eval_runs
WHERE workflow_id = $1
ORDER BY created_at DESC, id DESC
LIMIT $2 OFFSET $3;

-- name: ListCasesByEvalRun :many
SELECT * FROM eval_result_cases
WHERE eval_run_id = $1
ORDER BY case_id ASC;
